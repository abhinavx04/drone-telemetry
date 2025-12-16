from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Dict, Optional

from mavsdk import System
from mavsdk.telemetry import FlightMode as MavsdkFlightMode

from app.config import settings
from app.mqtt import normalized_to_payload, persist_normalized, publish_normalized
from app.schemas import NormalizedTelemetry, Position, TelemetryDerived, TelemetryFlags
from app.state import mavsdk_state, telemetry_cache

logger = logging.getLogger("mavsdk_ingestor")

# MAVSDK is the authoritative telemetry source.
# Raw MAVLink parsing is intentionally not used due to SysID=255 GCS proxy streams.

_FLIGHT_MODE_MAP: Dict[MavsdkFlightMode, str] = {
    MavsdkFlightMode.HOLD: "POS_HOLD",
    MavsdkFlightMode.READY: "POS_HOLD",
    MavsdkFlightMode.TAKEOFF: "MISSION",
    MavsdkFlightMode.MISSION: "MISSION",
    MavsdkFlightMode.RETURN_TO_LAUNCH: "RTL",
    MavsdkFlightMode.LAND: "LAND",
    MavsdkFlightMode.OFFBOARD: "OFFBOARD",
    MavsdkFlightMode.FOLLOW_ME: "MISSION",
    MavsdkFlightMode.UNKNOWN: "UNKNOWN",
}


def _map_flight_mode(mode: Optional[MavsdkFlightMode]) -> Optional[str]:
    if mode is None:
        return None
    return _FLIGHT_MODE_MAP.get(mode, mode.name if hasattr(mode, "name") else str(mode))


class MavsdkIngestor:
    """
    Async MAVSDK-based telemetry ingestor. Subscribes to PX4 telemetry via the GCS
    proxy, normalizes fields, updates in-memory cache/DB, and publishes MQTT at a
    controlled rate. Liveness is derived from telemetry timestamps; heartbeats are
    intentionally not used.
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._publish_interval = 1.0 / settings.publish_rate_hz if settings.publish_rate_hz > 0 else 0
        self._last_publish_ts: float = 0.0
        self._latest: Dict[str, Optional[object]] = {
            "position": None,
            "battery_pct": None,
            "flight_mode": None,
            "ground_speed_mps": None,
            "climb_rate_mps": None,
            "heading_deg": None,
            "source_timestamp": None,
        }

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="mavsdk-ingestor")
        logger.info(
            "[boot] DRONE_ID=%s LABEL=%s MAVSDK_URL=%s PUBLISH_RATE_HZ=%s",
            settings.drone_id,
            settings.drone_label,
            settings.mavsdk_url,
            settings.publish_rate_hz,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        mavsdk_state.update({"connected": False, "status": "disconnected"})

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                mavsdk_state.update(
                    {"connected": False, "status": "connecting", "last_error": None}
                )
                drone = System()
                await drone.connect(system_address=settings.mavsdk_url)
                mavsdk_state.update(
                    {
                        "connected": True,
                        "status": "connected",
                        "last_connect_ts": time.time(),
                    }
                )
                await self._consume(drone)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.error("MAVSDK connection error: %s", exc)
                mavsdk_state.update(
                    {"connected": False, "status": "disconnected", "last_error": str(exc)}
                )
                await asyncio.sleep(settings.mavsdk_connect_retry_s)

    async def _consume(self, drone: System) -> None:
        tasks = [
            asyncio.create_task(self._read_positions(drone)),
            asyncio.create_task(self._read_battery(drone)),
            asyncio.create_task(self._read_flight_mode(drone)),
            asyncio.create_task(self._read_velocity(drone)),
            asyncio.create_task(self._read_heading(drone)),
        ]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
        for t in done:
            if t.cancelled():
                continue
            exc = t.exception()
            if exc:
                logger.error("MAVSDK stream error: %s", exc)
                raise exc

    async def _read_positions(self, drone: System) -> None:
        async for pos in drone.telemetry.position():
            if self._stop.is_set():
                break
            self._latest["position"] = {
                "lat": pos.latitude_deg,
                "lon": pos.longitude_deg,
                "alt_m": pos.absolute_altitude_m,
            }
            source_ts = None
            try:
                source_ts = int(pos.timestamp_us / 1_000_000) if pos.timestamp_us else None
            except Exception:
                source_ts = None
            await self._maybe_publish(source_ts)

    async def _read_battery(self, drone: System) -> None:
        async for bat in drone.telemetry.battery():
            if self._stop.is_set():
                break
            pct = None
            try:
                if bat.remaining_percent is not None:
                    pct = max(0.0, min(100.0, float(bat.remaining_percent * 100.0)))
            except Exception:
                pct = None
            self._latest["battery_pct"] = pct
            await self._maybe_publish()

    async def _read_flight_mode(self, drone: System) -> None:
        async for fm in drone.telemetry.flight_mode():
            if self._stop.is_set():
                break
            self._latest["flight_mode"] = _map_flight_mode(fm)
            await self._maybe_publish()

    async def _read_velocity(self, drone: System) -> None:
        async for vel in drone.telemetry.velocity_ned():
            if self._stop.is_set():
                break
            try:
                vx = float(vel.north_m_s)
                vy = float(vel.east_m_s)
                vz = float(vel.down_m_s)
                self._latest["ground_speed_mps"] = math.sqrt(vx * vx + vy * vy)
                self._latest["climb_rate_mps"] = -vz
            except Exception:
                self._latest["ground_speed_mps"] = None
                self._latest["climb_rate_mps"] = None
            await self._maybe_publish()

    async def _read_heading(self, drone: System) -> None:
        async for att in drone.telemetry.attitude_euler():
            if self._stop.is_set():
                break
            try:
                self._latest["heading_deg"] = float(att.yaw_deg)
            except Exception:
                self._latest["heading_deg"] = None
            await self._maybe_publish()

    async def _maybe_publish(self, source_ts: Optional[int] = None) -> None:
        now = time.time()
        mavsdk_state["last_message_ts"] = now
        mavsdk_state["messages"] = int(mavsdk_state.get("messages") or 0) + 1

        if source_ts:
            self._latest["source_timestamp"] = source_ts

        if self._publish_interval > 0 and (now - self._last_publish_ts) < self._publish_interval:
            return

        normalized = self._build_normalized(now)
        if normalized is None:
            return

        self._last_publish_ts = now
        mavsdk_state["published"] = int(mavsdk_state.get("published") or 0) + 1
        payload = normalized_to_payload(normalized, include_ingest_source=True)
        await asyncio.gather(
            telemetry_cache.update(normalized),
            persist_normalized(normalized),
            asyncio.to_thread(publish_normalized, normalized, payload),
        )

    def _build_normalized(self, now: float) -> Optional[NormalizedTelemetry]:
        position_obj = None
        flags = TelemetryFlags(gps_lost=True, rc_lost=None, is_emergency=False)

        pos = self._latest.get("position")
        if pos:
            position_obj = Position(lat=pos["lat"], lon=pos["lon"], alt_m=pos.get("alt_m"))
            flags.gps_lost = False

        battery_pct = self._latest.get("battery_pct")
        if battery_pct is not None and battery_pct <= settings.emergency_battery_pct:
            flags.is_emergency = True

        derived = TelemetryDerived(
            ground_speed_mps=self._latest.get("ground_speed_mps"),
            climb_rate_mps=self._latest.get("climb_rate_mps"),
            heading_deg=self._latest.get("heading_deg"),
        )

        source_ts = self._latest.get("source_timestamp") or int(now)

        return NormalizedTelemetry(
            drone_id=settings.drone_id.strip(),
            source_timestamp=int(source_ts),
            ingest_timestamp=now,
            received_timestamp=now,
            position=position_obj,
            battery_pct=battery_pct,
            flight_mode=self._latest.get("flight_mode"),
            flags=flags,
            derived=derived,
        )

    def get_stats(self) -> Dict[str, object]:
        if not settings.ingest_debug_stats:
            return {}
        return {
            "last_message_ts": mavsdk_state.get("last_message_ts"),
            "messages": mavsdk_state.get("messages"),
            "published": mavsdk_state.get("published"),
            "publish_interval_s": self._publish_interval,
        }


_ingestor: Optional[MavsdkIngestor] = None


async def start_ingestor() -> None:
    global _ingestor
    if _ingestor is None:
        _ingestor = MavsdkIngestor()
    await _ingestor.start()


async def stop_ingestor() -> None:
    if _ingestor:
        await _ingestor.stop()


def get_ingestor_stats() -> Dict[str, object]:
    if _ingestor:
        return _ingestor.get_stats()
    return {}
