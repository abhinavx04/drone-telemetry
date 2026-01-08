from __future__ import annotations

import asyncio
import logging
import math
import socket
import select
import threading
import time
from typing import Dict, List, Optional

from pymavlink.dialects.v20 import ardupilotmega as mavlink2

from app.config import settings
from app.flight_tracker import get_tracker
from app.mqtt import normalized_to_payload, persist_normalized, publish_normalized, sanitize_json_value
from app.schemas import NormalizedTelemetry, Position, TelemetryDerived, TelemetryFlags
from app.state import drone_contexts, telemetry_cache

logger = logging.getLogger("mavlink_ingestor")


def _decode_px4_flight_mode(custom_mode: int) -> Optional[str]:
    """
    Convert PX4 custom_mode to human-readable flight mode string.
    PX4 flight modes: https://github.com/PX4/PX4-Autopilot/blob/main/src/modules/commander/px4_custom_mode.h
    """
    MAIN_MODE_MASK = 0xF0
    SUB_MODE_MASK = 0x0F

    main_mode = (custom_mode & MAIN_MODE_MASK) >> 4
    sub_mode = custom_mode & SUB_MODE_MASK  # noqa: F841

    mode_map = {
        1: "MANUAL",  # MANUAL
        2: "ALT_HOLD",  # ALTCTL
        3: "POS_HOLD",  # POSCTL
        4: "MISSION",  # AUTO
        5: "ACRO",  # ACRO
        6: "OFFBOARD",  # OFFBOARD
        7: "STABILIZED",  # STABILIZED
    }
    return mode_map.get(main_mode, "UNKNOWN")


class MavlinkIngestor:
    """
    UDP MAVLink ingestor (authoritative).
    Listens on UDP, normalizes telemetry, updates cache/DB, and publishes MQTT.
    """

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sockets: Dict[int, socket.socket] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._publish_interval = 1.0 / settings.publish_rate_hz if settings.publish_rate_hz > 0 else 0
        self._last_publish_ts: Dict[str, float] = {}
        self._latest: Dict[str, Dict[str, object]] = {}
        self._mav = mavlink2.MAVLink(None)
        self._mav.robust_parsing = True

    async def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._loop = asyncio.get_running_loop()
        self._stop.clear()
        await drone_contexts.start_gc()
        self._thread = threading.Thread(target=self._run, name="udp-mavlink-listener", daemon=True)
        self._thread.start()
        logger.info(
            "[boot] UDP_BIND=%s:%s-%s PUBLISH_RATE_HZ=%s",
            settings.udp_bind_host,
            settings.udp_bind_start_port,
            settings.udp_bind_end_port,
            settings.publish_rate_hz,
        )

    async def stop(self) -> None:
        self._stop.set()
        for sock in self._sockets.values():
            try:
                sock.close()
            except Exception:  # noqa: BLE001
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        await drone_contexts.stop_gc()

    def _run(self) -> None:
        start_port = settings.udp_bind_start_port
        end_port = settings.udp_bind_end_port
        if end_port < start_port:
            raise ValueError("UDP_BIND_END_PORT must be >= UDP_BIND_START_PORT")

        for port in range(start_port, end_port + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, settings.udp_recv_buffer_bytes)
            sock.bind((settings.udp_bind_host, port))
            self._sockets[port] = sock
        logger.info(
            "UDP listeners bound to %s:%s-%s (%s ports)",
            settings.udp_bind_host,
            start_port,
            end_port,
            len(self._sockets),
        )

        sockets_list = list(self._sockets.values())
        while not self._stop.is_set():
            if not sockets_list:
                time.sleep(0.1)
                continue

            ready, _, _ = select.select(sockets_list, [], [], 1.0)
            for sock in ready:
                try:
                    data, addr = sock.recvfrom(8192)
                except socket.error as exc:  # noqa: BLE001
                    logger.error("Socket error in UDP listener: %s", exc)
                    continue

                dest_port = sock.getsockname()[1]
                source_ip, _source_port = addr
                drone_id = f"udp:{dest_port}"
                try:
                    messages = self._parse_messages(data)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Dropped malformed MAVLink frame for %s: %s", drone_id, exc)
                    self._record_drop(drone_id)
                    continue

                for msg in messages:
                    try:
                        self._handle_message(msg, drone_id, source_ip, dest_port)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Failed processing MAVLink msg for %s: %s", drone_id, exc, exc_info=True)

    def _parse_messages(self, data: bytes) -> List[object]:
        messages: List[object] = []
        for b in data:
            msg = self._mav.parse_char(bytes([b]))
            if msg:
                messages.append(msg)
        return messages

    def _handle_message(self, msg: object, drone_id: str, source_ip: str, dest_port: int) -> None:
        msg_type = msg.get_type()
        if msg_type not in {
            "GLOBAL_POSITION_INT",
            "GPS_RAW_INT",
            "BATTERY_STATUS",
            "VFR_HUD",
            "ATTITUDE",
            "HEARTBEAT",
        }:
            return

        latest = self._latest.setdefault(
            drone_id,
            {
                "lat": None,
                "lon": None,
                "alt_m": None,
                "battery_pct": None,
                "flight_mode": None,
                "ground_speed_mps": None,
                "climb_rate_mps": None,
                "heading_deg": None,
                "gps_fix": None,
                "source_timestamp": None,
            },
        )

        now = time.time()
        source_ts = None

        if msg_type == "GLOBAL_POSITION_INT":
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            if lat == 0.0 and lon == 0.0:
                return
            latest["lat"] = lat
            latest["lon"] = lon
            latest["alt_m"] = msg.alt / 1000.0
            latest["relative_alt_m"] = msg.relative_alt / 1000.0
            source_ts = getattr(msg, "time_boot_ms", None)
            if source_ts is not None:
                source_ts = int(source_ts / 1000)

        elif msg_type == "GPS_RAW_INT":
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            if lat == 0.0 and lon == 0.0:
                return
            latest["lat"] = lat
            latest["lon"] = lon
            latest["gps_fix"] = msg.fix_type >= 2
            source_ts = getattr(msg, "time_usec", None)
            if source_ts is not None:
                source_ts = int(source_ts / 1_000_000)

        elif msg_type == "BATTERY_STATUS":
            if msg.battery_remaining is not None and msg.battery_remaining >= 0:
                latest["battery_pct"] = float(msg.battery_remaining)
            else:
                latest["battery_pct"] = None
            try:
                voltages = getattr(msg, "voltages", []) or []
                latest["voltage_v"] = voltages[0] / 100.0 if voltages else None
            except Exception:  # noqa: BLE001
                latest["voltage_v"] = None

        elif msg_type == "VFR_HUD":
            latest["ground_speed_mps"] = msg.groundspeed
            latest["climb_rate_mps"] = msg.climb
            latest["heading_deg"] = msg.heading

        elif msg_type == "ATTITUDE":
            try:
                latest["heading_deg"] = math.degrees(msg.yaw) % 360.0
            except Exception:  # noqa: BLE001
                latest["heading_deg"] = None

        elif msg_type == "HEARTBEAT":
            latest["flight_mode"] = _decode_px4_flight_mode(getattr(msg, "custom_mode", 0))
            base_mode = getattr(msg, "base_mode", 0)
            is_armed = bool(base_mode & 0x80)
            try:
                sysid = msg.get_srcSystem()
            except Exception:
                sysid = None
            self._submit_heartbeat(drone_id, is_armed, dest_port, sysid)

        if source_ts:
            latest["source_timestamp"] = source_ts

        should_publish = self._publish_interval == 0 or (
            now - self._last_publish_ts.get(drone_id, 0)
        ) >= self._publish_interval
        if should_publish:
            normalized = self._build_normalized(drone_id, latest, now)
            if normalized:
                self._last_publish_ts[drone_id] = now
                self._dispatch(drone_id, source_ip, dest_port, normalized)

    def _build_normalized(
        self, drone_id: str, latest: Dict[str, object], now: float
    ) -> Optional[NormalizedTelemetry]:
        position_obj = None
        gps_lost = True

        if latest.get("lat") is not None and latest.get("lon") is not None:
            position_obj = Position(lat=float(latest["lat"]), lon=float(latest["lon"]), alt_m=latest.get("alt_m"))
            gps_lost = False
        gps_fix = latest.get("gps_fix")
        if gps_fix is False:
            gps_lost = True

        battery_pct = latest.get("battery_pct")
        is_emergency = False
        if battery_pct is not None and battery_pct <= settings.emergency_battery_pct:
            is_emergency = True

        derived = TelemetryDerived(
            ground_speed_mps=latest.get("ground_speed_mps"),
            climb_rate_mps=latest.get("climb_rate_mps"),
            heading_deg=latest.get("heading_deg"),
        )

        source_ts = latest.get("source_timestamp") or int(now)

        return NormalizedTelemetry(
            drone_id=drone_id,
            source_timestamp=int(source_ts),
            ingest_timestamp=now,
            received_timestamp=now,
            position=position_obj,
            battery_pct=battery_pct,
            flight_mode=latest.get("flight_mode"),
            flags=TelemetryFlags(gps_lost=gps_lost, rc_lost=None, is_emergency=is_emergency),
            derived=derived,
        )

    def _dispatch(self, drone_id: str, source_ip: str, dest_port: int, normalized: NormalizedTelemetry) -> None:
        if not self._loop:
            return

        async_calls = [
            (telemetry_cache.update(normalized), 1.0),
            (persist_normalized(normalized), 2.0),
            (drone_contexts.upsert(drone_id, source_ip, dest_port, normalized), 1.0),
        ]

        tracker = get_tracker()
        if tracker and self._loop:
            future = asyncio.run_coroutine_threadsafe(
                tracker.handle_normalized(normalized, dest_port), self._loop
            )
            future.add_done_callback(
                lambda fut: logger.error("Flight tracker telemetry failed: %s", fut.exception())
                if fut.exception()
                else None
            )

        for coro, timeout_s in async_calls:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            try:
                future.result(timeout=timeout_s)
            except Exception as exc:  # noqa: BLE001
                logger.error("Async bridge failure for %s: %s", drone_id, exc)

        payload = normalized_to_payload(normalized, include_ingest_source=True)
        payload = sanitize_json_value(payload)
        try:
            publish_normalized(normalized, payload)
        except Exception as exc:  # noqa: BLE001
            logger.error("MQTT publish failed for %s: %s", drone_id, exc)

    def _record_drop(self, drone_id: str) -> None:
        if not self._loop:
            return
        future = asyncio.run_coroutine_threadsafe(drone_contexts.drop_only(drone_id), self._loop)
        try:
            future.result(timeout=1.0)
        except Exception:
            pass

    def _submit_heartbeat(self, drone_id: str, is_armed: bool, dest_port: int, sysid: Optional[int]) -> None:
        tracker = get_tracker()
        if not tracker or not self._loop:
            return
        future = asyncio.run_coroutine_threadsafe(
            tracker.handle_heartbeat(drone_id, is_armed=is_armed, udp_port=dest_port, sysid=sysid),
            self._loop,
        )
        future.add_done_callback(
            lambda fut: logger.error("Flight tracker heartbeat bridge failed for %s: %s", drone_id, fut.exception())
            if fut.exception()
            else None
        )

    def get_stats(self) -> Dict[str, object]:
        if not settings.ingest_debug_stats:
            return {}
        return {
            "publish_interval_s": self._publish_interval,
            "last_publish_ts": self._last_publish_ts,
        }


_ingestor: Optional[MavlinkIngestor] = None


async def start_ingestor() -> None:
    global _ingestor
    if _ingestor is None:
        _ingestor = MavlinkIngestor()
    await _ingestor.start()


async def stop_ingestor() -> None:
    if _ingestor:
        await _ingestor.stop()


def get_ingestor_stats() -> Dict[str, object]:
    if _ingestor:
        return _ingestor.get_stats()
    return {}
