from __future__ import annotations

import logging
import math
import socket
import threading
import time
from typing import Dict, Optional

from pymavlink import mavutil

from app.config import settings
from app.mqtt import publish_normalized, normalized_to_payload, persist_normalized
from app.schemas import NormalizedTelemetry, Position, TelemetryDerived, TelemetryFlags
from app.state import telemetry_cache

logger = logging.getLogger("mavlink_ingestor")


class _PerDroneStats:
    def __init__(self) -> None:
        self.last_seen_ts: Optional[float] = None
        self.packets: int = 0
        self.messages: int = 0


class MavlinkIngestor:
    """
    Dedicated daemon thread that listens for raw MAVLink over UDP, parses frames
    with robust parsing, normalizes telemetry, and publishes it to the in-memory
    cache and MQTT. It does NOT require heartbeats, and it tolerates mixed v1/v2.
    """

    def __init__(self, loop):
        self.loop = loop
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.stats: Dict[str, _PerDroneStats] = {}
        self._last_published: Dict[str, dict] = {}

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run, name="mavlink-ingestor", daemon=True)
        self.thread.start()
        logger.info("Started MAVLink UDP ingestor on %s:%s", settings.mavlink_udp_host, settings.mavlink_udp_port)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Stopped MAVLink UDP ingestor")

    def _run(self) -> None:
        mavutil.set_dialect(settings.mavlink_dialect)
        parser = mavutil.mavlink.MAVLink(None)
        parser.robust_parsing = settings.mavlink_robust_parsing
        parser.srcSystem = 255
        parser.srcComponent = 0
        logger.info(
            "MAVLink UDP ingestor binding %s:%s (dialect=%s robust=%s)",
            settings.mavlink_udp_host,
            settings.mavlink_udp_port,
            settings.mavlink_dialect,
            settings.mavlink_robust_parsing,
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((settings.mavlink_udp_host, settings.mavlink_udp_port))
        sock.settimeout(1.0)

        while not self.stop_event.is_set():
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("UDP recv error: %s", exc)
                continue

            src_ip, src_port = addr[0], addr[1]
            drone_id = f"drone_{src_ip}_{src_port}"
            now = time.time()
            stats = self.stats.setdefault(drone_id, _PerDroneStats())
            stats.last_seen_ts = now
            stats.packets += 1

            for byte in data:
                try:
                    msg = parser.parse_char(bytes([byte]))
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Parse error for %s: %s", drone_id, exc)
                    continue

                if not msg:
                    continue
                stats.messages += 1
                telemetry = self._to_normalized(drone_id, msg, now)
                if telemetry is None:
                    continue
                self._deliver(telemetry)

    def _deliver(self, telemetry: NormalizedTelemetry) -> None:
        # Update cache asynchronously on the FastAPI loop
        try:
            import asyncio

            # Ensure we target the server's loop without blocking it.
            asyncio.run_coroutine_threadsafe(telemetry_cache.update(telemetry), self.loop)
            asyncio.run_coroutine_threadsafe(persist_normalized(telemetry), self.loop)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to schedule cache update for %s: %s", telemetry.drone_id, exc)

        # Publish to MQTT only when data changes to avoid chatter
        payload = normalized_to_payload(telemetry, include_ingest_source=True)
        last_payload = self._last_published.get(telemetry.drone_id)
        if last_payload != payload:
            publish_normalized(telemetry, payload)
            self._last_published[telemetry.drone_id] = payload

    def _to_normalized(self, drone_id: str, msg, ingest_ts: float) -> Optional[NormalizedTelemetry]:
        mtype = msg.get_type()
        # Default fields
        position = None
        battery_pct = None
        flight_mode = None
        flags = TelemetryFlags(gps_lost=False, rc_lost=None, is_emergency=False)
        derived = TelemetryDerived(ground_speed_mps=None, climb_rate_mps=None, heading_deg=None)

        source_ts = int(ingest_ts)
        try:
            if hasattr(msg, "time_boot_ms") and msg.time_boot_ms is not None:
                source_ts = int(msg.time_boot_ms / 1000)
            elif hasattr(msg, "time_usec") and msg.time_usec is not None:
                source_ts = int(msg.time_usec / 1_000_000)
        except Exception:
            source_ts = int(ingest_ts)

        if mtype == "HEARTBEAT":
            # Do not depend on heartbeats for readiness; best-effort flight mode only.
            try:
                flight_mode = mavutil.mode_string_v10(msg)
            except Exception:
                flight_mode = None

        elif mtype == "GLOBAL_POSITION_INT":
            lat = msg.lat / 1e7 if msg.lat is not None else None
            lon = msg.lon / 1e7 if msg.lon is not None else None
            alt_m = msg.alt / 1000.0 if msg.alt is not None else None
            if lat is not None and lon is not None:
                position = Position(lat=lat, lon=lon, alt_m=alt_m)
                flags.gps_lost = False
            else:
                flags.gps_lost = True

            try:
                if msg.vx is not None and msg.vy is not None:
                    vx = msg.vx / 100.0
                    vy = msg.vy / 100.0
                    derived.ground_speed_mps = math.sqrt(vx * vx + vy * vy)
                if msg.vz is not None:
                    derived.climb_rate_mps = -msg.vz / 100.0
                if getattr(msg, "hdg", None) not in (None, 65535):
                    derived.heading_deg = msg.hdg / 100.0
            except Exception:
                pass

        elif mtype == "LOCAL_POSITION_NED":
            try:
                vx = float(msg.vx)
                vy = float(msg.vy)
                vz = float(msg.vz)
                derived.ground_speed_mps = math.sqrt(vx * vx + vy * vy)
                derived.climb_rate_mps = -vz
            except Exception:
                pass

        elif mtype == "SYS_STATUS":
            if msg.battery_remaining is not None and msg.battery_remaining >= 0:
                battery_pct = max(0.0, min(100.0, float(msg.battery_remaining)))
            if battery_pct is not None and battery_pct <= settings.emergency_battery_pct:
                flags.is_emergency = True

        elif mtype == "VFR_HUD":
            try:
                derived.ground_speed_mps = float(msg.groundspeed)
            except Exception:
                pass
            try:
                if msg.heading not in (None, 361):
                    derived.heading_deg = float(msg.heading)
            except Exception:
                pass
            try:
                derived.climb_rate_mps = float(msg.climb)
            except Exception:
                pass

        elif mtype == "ATTITUDE":
            try:
                derived.heading_deg = math.degrees(float(msg.yaw))
            except Exception:
                pass

        elif mtype == "GPS_RAW_INT":
            fix_type = getattr(msg, "fix_type", None)
            if fix_type is not None and fix_type < 3:
                flags.gps_lost = True
            elif fix_type is not None:
                flags.gps_lost = False

        else:
            # Ignore unsupported messages safely
            return None

        return NormalizedTelemetry(
            drone_id=drone_id,
            source_timestamp=source_ts,
            ingest_timestamp=ingest_ts,
            position=position,
            battery_pct=battery_pct,
            flight_mode=flight_mode,
            flags=flags,
            derived=derived,
        )

    def get_stats(self) -> Dict[str, dict]:
        if not settings.ingest_debug_stats:
            return {}
        out: Dict[str, dict] = {}
        for drone_id, s in self.stats.items():
            out[drone_id] = {
                "last_seen_ts": s.last_seen_ts,
                "packets": s.packets,
                "messages": s.messages,
            }
        return out


_ingestor: Optional[MavlinkIngestor] = None


def start_ingestor(loop) -> None:
    global _ingestor
    if _ingestor is None:
        _ingestor = MavlinkIngestor(loop)
    _ingestor.start()


def stop_ingestor() -> None:
    if _ingestor:
        _ingestor.stop()


def get_ingestor_stats() -> Dict[str, dict]:
    if _ingestor:
        return _ingestor.get_stats()
    return {}
