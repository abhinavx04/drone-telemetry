from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
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


@dataclass
class DroneContext:
    drone_id: str
    source_ip: str
    source_port: int
    last_seen_ts: float
    status: str
    telemetry: Optional[NormalizedTelemetry] = None
    ingest_stats: Dict[str, float | int] = field(
        default_factory=lambda: {
            "packets_received": 0,
            "packets_dropped": 0,
            "last_packet_ts": None,
        }
    )


class DroneContextStore:
    """
    Thread-safe per-drone contexts for UDP ingestion. The UDP listener thread
    calls into these async methods via asyncio.run_coroutine_threadsafe.
    """

    def __init__(self, stale_after_s: int, offline_after_s: int) -> None:
        self.stale_after_s = stale_after_s
        self.offline_after_s = offline_after_s
        self._data: Dict[str, DroneContext] = {}
        self._lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._gc_task: Optional[asyncio.Task] = None
        self.gc_evictions = 0

    def _status(self, now: float, last_seen_ts: Optional[float]) -> str:
        if last_seen_ts is None:
            return "offline"
        age = now - last_seen_ts
        if age <= self.stale_after_s:
            return "online"
        if age <= self.offline_after_s:
            return "stale"
        return "offline"

    async def upsert(
        self,
        drone_id: str,
        source_ip: str,
        source_port: int,
        telemetry: NormalizedTelemetry,
        dropped: int = 0,
    ) -> None:
        now = time.time()
        async with self._lock:
            ctx = self._data.get(
                drone_id,
                DroneContext(
                    drone_id=drone_id,
                    source_ip=source_ip,
                    source_port=source_port,
                    last_seen_ts=now,
                    status="offline",
                ),
            )
            ctx.source_ip = source_ip
            ctx.source_port = source_port
            ctx.telemetry = telemetry
            ctx.last_seen_ts = telemetry.received_timestamp or telemetry.ingest_timestamp
            ctx.ingest_stats["packets_received"] = int(ctx.ingest_stats.get("packets_received", 0)) + 1
            ctx.ingest_stats["packets_dropped"] = int(ctx.ingest_stats.get("packets_dropped", 0)) + int(dropped)
            ctx.ingest_stats["last_packet_ts"] = ctx.last_seen_ts
            ctx.status = self._status(now, ctx.last_seen_ts)
            self._data[drone_id] = ctx

    async def drop_only(self, drone_id: str, dropped: int = 1) -> None:
        """Record a dropped packet for an existing context."""
        async with self._lock:
            ctx = self._data.get(drone_id)
            if not ctx:
                return
            ctx.ingest_stats["packets_dropped"] = int(ctx.ingest_stats.get("packets_dropped", 0)) + int(dropped)

    async def snapshot(self, drone_id: Optional[str] = None) -> dict:
        now = time.time()
        async with self._lock:
            if drone_id:
                ctx = self._data.get(drone_id)
                if not ctx:
                    return {"status": "unknown"}
                age = now - float(ctx.last_seen_ts)
                return {
                    "drone_id": ctx.drone_id,
                    "status": self._status(now, ctx.last_seen_ts),
                    "last_seen_ts": ctx.last_seen_ts,
                    "source_ip": ctx.source_ip,
                    "source_port": ctx.source_port,
                    "telemetry_version": getattr(ctx.telemetry, "version", None),
                    "ingest_stats": dict(ctx.ingest_stats),
                    "age_s": age,
                }

            total_packets = sum(int(c.ingest_stats.get("packets_received", 0)) for c in self._data.values())
            total_dropped = sum(int(c.ingest_stats.get("packets_dropped", 0)) for c in self._data.values())
            return {
                "active_drones": len(self._data),
                "total_packets_received": total_packets,
                "total_packets_dropped": total_dropped,
                "gc_evictions": self.gc_evictions,
                "drones": {
                    did: {
                        "status": self._status(now, ctx.last_seen_ts),
                        "last_seen_ts": ctx.last_seen_ts,
                        "source_ip": ctx.source_ip,
                        "source_port": ctx.source_port,
                        "ingest_stats": dict(ctx.ingest_stats),
                    }
                    for did, ctx in self._data.items()
                },
            }

    async def start_gc(self) -> None:
        if self._gc_task and not self._gc_task.done():
            return
        self._stop.clear()
        self._gc_task = asyncio.create_task(self._gc_offline_drones(), name="drone-context-gc")

    async def stop_gc(self) -> None:
        self._stop.set()
        if self._gc_task:
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass

    async def _gc_offline_drones(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(settings.gc_interval_sec)
            now = time.time()
            to_delete: list[str] = []
            async with self._lock:
                for drone_id, ctx in self._data.items():
                    age = now - ctx.last_seen_ts
                    status = self._status(now, ctx.last_seen_ts)
                    if status == "offline" and age > settings.gc_offline_after_sec:
                        to_delete.append(drone_id)
                for drone_id in to_delete:
                    ctx = self._data.get(drone_id)
                    last_age = now - ctx.last_seen_ts if ctx else None
                    logger.info(
                        "GC: Removing offline drone %s (offline for %s seconds)",
                        drone_id,
                        int(last_age) if last_age is not None else "unknown",
                    )
                    self._data.pop(drone_id, None)
                    self.gc_evictions += 1


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

# Authoritative UDP ingestion contexts.
drone_contexts = DroneContextStore(
    stale_after_s=settings.stale_after_sec,
    offline_after_s=settings.offline_after_sec,
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


async def get_mavlink_snapshot(drone_id: Optional[str] = None) -> dict:
    """
    Returns per-drone or aggregate MAVLink ingestion state.
    """
    return await drone_contexts.snapshot(drone_id)

