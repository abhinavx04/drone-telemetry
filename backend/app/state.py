from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

from app.config import settings
from app.schemas import (
    BatteryOut,
    DroneSummary,
    NormalizedTelemetry,
    Position,
    TelemetryDerived,
    TelemetryFlags,
    TelemetryLatestOut,
)

logger = logging.getLogger(__name__)


SERVICE_START_TIME = time.time()

# Updated by the MQTT client; read by the API layer for health reporting.
mqtt_state: Dict[str, Optional[object]] = {
    "connected": False,
    "last_message_ts": None,
    "last_error": None,
}

# Updated by the MAVSDK ingestor for health and debug reporting.
mavsdk_state: Dict[str, Optional[object]] = {
    "connected": False,
    "status": "disconnected",
    "last_message_ts": None,
    "last_connect_ts": None,
    "last_error": None,
    "messages": 0,
    "published": 0,
    "drone_id": settings.drone_id,
    "drone_label": settings.drone_label,
}


class TelemetryCache:
    """
    Single-writer (ingestion) / multi-reader (API) in-memory cache for the
    most recent telemetry per drone. Stores only the latest sample to keep
    memory bounded and response times predictable.
    """

    def __init__(self, stale_after_s: int, offline_after_s: int, max_drones: int):
        self.stale_after_s = stale_after_s
        self.offline_after_s = offline_after_s
        self.max_drones = max_drones
        self._data: Dict[str, Dict[str, object]] = {}
        self._lock = asyncio.Lock()

    def _status(self, now: float, last_seen_ts: Optional[float]) -> str:
        if last_seen_ts is None:
            return "offline"
        age = now - last_seen_ts
        if age <= self.stale_after_s:
            return "online"
        if age <= self.offline_after_s:
            return "stale"
        return "offline"

    def _evict_if_needed(self) -> None:
        if len(self._data) <= self.max_drones:
            return
        # Evict the oldest entries first to stay within bounds.
        sorted_items = sorted(self._data.items(), key=lambda item: item[1].get("last_seen_ts") or 0)
        excess = len(self._data) - self.max_drones
        for drone_id, _ in sorted_items[:excess]:
            logger.warning("Evicting drone %s from cache to enforce max_drones=%s", drone_id, self.max_drones)
            self._data.pop(drone_id, None)

    async def update(self, telemetry: NormalizedTelemetry) -> None:
        async with self._lock:
            entry = self._data.get(
                telemetry.drone_id,
                {
                    "version": 0,
                    "position": None,
                    "battery_pct": None,
                    "flight_mode": None,
                    "flags": TelemetryFlags().model_dump(),
                    "derived": TelemetryDerived().model_dump(),
                },
            )

            entry["last_seen_ts"] = telemetry.received_timestamp or telemetry.ingest_timestamp
            entry["received_timestamp"] = telemetry.received_timestamp
            entry["source_timestamp"] = telemetry.source_timestamp
            if telemetry.position is not None:
                entry["position"] = telemetry.position.model_dump()
            elif telemetry.flags.gps_lost:
                entry["position"] = None

            if telemetry.battery_pct is not None:
                entry["battery_pct"] = telemetry.battery_pct
            if telemetry.flight_mode is not None:
                entry["flight_mode"] = telemetry.flight_mode

            entry["flags"] = telemetry.flags.model_dump()
            entry["derived"] = telemetry.derived.model_dump()
            entry["version"] = int(entry.get("version", 0)) + 1

            self._data[telemetry.drone_id] = entry
            self._evict_if_needed()

    async def list_summaries(self) -> list[DroneSummary]:
        now = time.time()
        async with self._lock:
            results: list[DroneSummary] = []
            for drone_id, entry in self._data.items():
                status = self._status(now, entry.get("last_seen_ts"))
                results.append(
                    DroneSummary(
                        id=drone_id,
                        status=status,
                        last_seen_ts=int(entry["last_seen_ts"]) if entry.get("last_seen_ts") else None,
                        battery_pct=entry.get("battery_pct"),
                        flight_mode=entry.get("flight_mode"),
                        position=Position(**entry["position"]) if entry.get("position") else None,
                    )
                )
            return results

    async def get_latest(self, drone_id: str) -> Optional[TelemetryLatestOut]:
        now = time.time()
        async with self._lock:
            entry = self._data.get(drone_id)
            if entry is None:
                return None

            status = self._status(now, entry.get("last_seen_ts"))
            return TelemetryLatestOut(
                id=drone_id,
                status=status,
                last_seen_ts=int(entry["last_seen_ts"]) if entry.get("last_seen_ts") else None,
                source_timestamp=int(entry["source_timestamp"]) if entry.get("source_timestamp") else None,
                received_timestamp=int(entry["received_timestamp"]) if entry.get("received_timestamp") else None,
                position=Position(**entry["position"]) if entry.get("position") else None,
                battery=BatteryOut(pct=entry.get("battery_pct"), voltage_v=None),
                flight_mode=entry.get("flight_mode"),
                flags=TelemetryFlags(**entry.get("flags", {})),
                derived=TelemetryDerived(**entry.get("derived", {})),
                version=int(entry.get("version", 0)),
            )


telemetry_cache = TelemetryCache(
    stale_after_s=settings.stale_after_sec,
    offline_after_s=settings.offline_after_sec,
    max_drones=settings.max_drones,
)


def get_mqtt_snapshot() -> dict:
    """
    Returns a copy of the MQTT connectivity state with a computed lag if
    messages have been seen.
    """
    last_ts = mqtt_state.get("last_message_ts")
    lag_ms = None
    if last_ts:
        lag_ms = int((time.time() - float(last_ts)) * 1000)
    return {
        "connected": mqtt_state.get("connected", False),
        "last_message_ts": last_ts,
        "lag_ms": lag_ms,
        "last_error": mqtt_state.get("last_error"),
    }


def get_mavsdk_snapshot() -> dict:
    """
    Returns a copy of the MAVSDK connectivity state with computed lag.
    """
    last_ts = mavsdk_state.get("last_message_ts")
    now = time.time()
    lag_ms = None
    if last_ts:
        lag_ms = int((now - float(last_ts)) * 1000)
    status = mavsdk_state.get("status") or "disconnected"
    if last_ts:
        age = now - float(last_ts)
        if age > settings.mavsdk_disconnected_after_s:
            status = "disconnected"
        elif age > settings.mavsdk_degraded_after_s:
            status = "degraded"
        else:
            status = "connected"
    return {
        "connected": mavsdk_state.get("connected", False),
        "status": status,
        "last_message_ts": last_ts,
        "lag_ms": lag_ms,
        "last_connect_ts": mavsdk_state.get("last_connect_ts"),
        "last_error": mavsdk_state.get("last_error"),
        "messages": mavsdk_state.get("messages"),
        "published": mavsdk_state.get("published"),
        "drone_id": mavsdk_state.get("drone_id"),
        "drone_label": mavsdk_state.get("drone_label"),
    }

