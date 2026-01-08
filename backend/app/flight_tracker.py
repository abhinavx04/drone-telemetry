from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from sqlalchemy import text

from app.config import settings
from app.db import AsyncSessionLocal
from app.schemas import NormalizedTelemetry

logger = logging.getLogger("flight_tracker")


@dataclass
class FlightMetrics:
    max_altitude_m: Optional[float] = None
    max_speed_mps: Optional[float] = None
    battery_start_pct: Optional[float] = None
    battery_end_pct: Optional[float] = None
    gps_issues_count: int = 0
    emergency_events_count: int = 0


@dataclass
class FlightState:
    flight_id: str
    drone_id: str
    flight_count: int
    start_ts: int
    last_heartbeat_ts: float
    last_telemetry_ts: float
    last_armed_state: bool
    last_state_change_ts: float
    metrics: FlightMetrics = field(default_factory=FlightMetrics)


class FlightTracker:
    """
    Tracks ARM/DISARM, creates flight records, and scopes telemetry to flights.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: Dict[str, FlightState] = {}
        self._armed_state: Dict[str, bool] = {}
        self._state_change_at: Dict[str, float] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        await self._recover_open_flights()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop(), name="flight-cleanup")
        logger.info("FlightTracker ready with %s active flights", len(self._active))

    async def stop(self) -> None:
        self._stop.set()
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def handle_heartbeat(
        self, drone_id: str, is_armed: bool, udp_port: Optional[int], sysid: Optional[int] = None
    ) -> None:
        """
        Entry point for the UDP ingestion thread. Debounces arm/disarm and starts/stops flights.
        """
        now = time.time()
        if not drone_id.startswith("udp:"):
            logger.warning("Ignoring heartbeat with unexpected drone_id format: %s", drone_id)
            return

        await self._ensure_registry(drone_id, udp_port, sysid, int(now))

        async with self._lock:
            last_state = self._armed_state.get(drone_id)
            last_change = self._state_change_at.get(drone_id, 0.0)

            logger.debug(
                "Heartbeat for %s: is_armed=%s last_state=%s last_change_ago=%.2fs",
                drone_id, is_armed, last_state, now - last_change if last_change > 0 else 0
            )

            if last_state is not None and last_state == is_armed:
                # Update last heartbeat time for active flight
                if drone_id in self._active:
                    self._active[drone_id].last_heartbeat_ts = now
                self._state_change_at[drone_id] = now
                return

            if now - last_change < 2.0:
                logger.debug("Debounced arm state change for %s (%.2fs)", drone_id, now - last_change)
                return

            self._armed_state[drone_id] = is_armed
            self._state_change_at[drone_id] = now

        if is_armed:
            logger.info("ARM detected for %s - starting flight", drone_id)
            await self._start_flight(drone_id, udp_port, now)
        else:
            logger.info("DISARM detected for %s - closing flight", drone_id)
            await self._close_flight(drone_id, now, auto_closed=False)

    async def handle_normalized(self, normalized: NormalizedTelemetry, udp_port: Optional[int] = None) -> None:
        """
        Persist flight-scoped telemetry and update metrics if a flight is active.
        """
        now = time.time()
        await self._ensure_registry(normalized.drone_id, udp_port, None, int(now))

        async with self._lock:
            state = self._active.get(normalized.drone_id)
        if not state:
            return

        # Update last telemetry timestamp
        async with self._lock:
            if normalized.drone_id in self._active:
                self._active[normalized.drone_id].last_telemetry_ts = now

        await self._persist_flight_telemetry(state.flight_id, normalized)

        # Update in-memory metrics for summary creation.
        async with self._lock:
            current = self._active.get(normalized.drone_id)
            if not current:
                return
            metrics = current.metrics
            if normalized.position and normalized.position.alt_m is not None:
                if metrics.max_altitude_m is None or normalized.position.alt_m > metrics.max_altitude_m:
                    metrics.max_altitude_m = float(normalized.position.alt_m)
            if normalized.derived.ground_speed_mps is not None:
                speed = float(normalized.derived.ground_speed_mps)
                if metrics.max_speed_mps is None or speed > metrics.max_speed_mps:
                    metrics.max_speed_mps = speed
            if normalized.battery_pct is not None:
                if metrics.battery_start_pct is None:
                    metrics.battery_start_pct = float(normalized.battery_pct)
                metrics.battery_end_pct = float(normalized.battery_pct)
            if normalized.flags.gps_lost:
                metrics.gps_issues_count += 1
            if normalized.flags.is_emergency:
                metrics.emergency_events_count += 1
            current.metrics = metrics
            self._active[normalized.drone_id] = current

    async def close_stale_open_flights(self) -> None:
        cutoff = int(time.time() - settings.flight_auto_close_after_sec)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT flight_id, drone_id, start_timestamp, flight_count FROM flights WHERE end_timestamp IS NULL")
            )
            rows = result.mappings().all()
        for row in rows:
            if row["start_timestamp"] and row["start_timestamp"] < cutoff:
                async with self._lock:
                    self._active.pop(row["drone_id"], None)
                    self._armed_state[row["drone_id"]] = False
                    self._state_change_at[row["drone_id"]] = time.time()
                await self._finalize_flight_by_id(
                    row["flight_id"],
                    row["drone_id"],
                    row["flight_count"],
                    start_ts=int(row["start_timestamp"]),
                    end_ts=int(time.time()),
                    auto_closed=True,
                )

    async def _recover_open_flights(self) -> None:
        """
        Restore in-progress flights on startup; auto-close stale ones.
        """
        now = int(time.time())
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT flight_id, drone_id, flight_count, start_timestamp FROM flights WHERE end_timestamp IS NULL")
            )
            rows = result.mappings().all()

        async with self._lock:
            for row in rows:
                start_ts = int(row["start_timestamp"])
                flight_id = row["flight_id"]
                drone_id = row["drone_id"]
                flight_count = int(row["flight_count"])
                if start_ts < now - settings.flight_auto_close_after_sec:
                    # Auto-close stale flight.
                    await self._finalize_flight_by_id(
                        flight_id, drone_id, flight_count, start_ts=start_ts, end_ts=now, auto_closed=True
                    )
                    continue
                self._active[drone_id] = FlightState(
                    flight_id=flight_id,
                    drone_id=drone_id,
                    flight_count=flight_count,
                    start_ts=start_ts,
                    last_heartbeat_ts=time.time(),
                    last_telemetry_ts=time.time(),
                    last_armed_state=True,
                    last_state_change_ts=time.time(),
                )
                self._armed_state[drone_id] = True
                self._state_change_at[drone_id] = time.time()
                logger.info("Recovered in-progress flight %s for %s", flight_id, drone_id)

    async def _check_telemetry_timeout(self) -> None:
        """
        Close flights for drones that haven't sent telemetry recently.
        Handles cases where drone/GCS is turned off without sending DISARM.
        """
        from app.state import telemetry_cache

        timeout_sec = settings.flight_telemetry_timeout_sec
        now = time.time()

        async with self._lock:
            active_copy = dict(self._active)

        for drone_id, state in active_copy.items():
            # Get last seen timestamp from telemetry cache
            snapshot = await telemetry_cache.get_latest(drone_id)
            if snapshot is None:
                # Drone unknown, close flight
                logger.info("Closing flight for %s: drone no longer in telemetry cache", drone_id)
                await self._close_flight(drone_id, now, auto_closed=True)
                continue

            last_seen = snapshot.last_seen_ts
            if last_seen is None:
                logger.info("Closing flight for %s: no last_seen timestamp", drone_id)
                await self._close_flight(drone_id, now, auto_closed=True)
                continue

            # Use last telemetry time from flight state, fallback to cache
            last_telemetry = state.last_telemetry_ts if state.last_telemetry_ts > 0 else last_seen
            age = now - last_telemetry

            if age > timeout_sec:
                # Check if drone is offline/stale
                if snapshot.status in ["offline", "stale"]:
                    logger.info(
                        "Closing flight for %s: no telemetry for %d seconds (status: %s, last_telemetry_age: %.1fs)",
                        drone_id, int(age), snapshot.status, age
                    )
                    await self._close_flight(drone_id, now, auto_closed=True)
                else:
                    logger.debug(
                        "Flight %s has no telemetry for %d seconds but drone status is %s - keeping open",
                        drone_id, int(age), snapshot.status
                    )

    async def _cleanup_loop(self) -> None:
        # Check telemetry timeout every minute for faster response
        telemetry_check_interval = min(60, settings.flight_telemetry_timeout_sec // 2)
        last_telemetry_check = 0.0

        while not self._stop.is_set():
            try:
                # Check telemetry timeout more frequently than full cleanup
                now = time.time()
                if now - last_telemetry_check >= telemetry_check_interval:
                    try:
                        await self._check_telemetry_timeout()
                        last_telemetry_check = now
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Telemetry timeout check failed: %s", exc, exc_info=True)

                # Wait for cleanup interval or stop event
                await asyncio.wait_for(self._stop.wait(), timeout=settings.flight_cleanup_interval_sec)
            except asyncio.TimeoutError:
                try:
                    await self.close_stale_open_flights()
                    # Also check telemetry timeout
                    await self._check_telemetry_timeout()
                    last_telemetry_check = time.time()
                except Exception as exc:  # noqa: BLE001
                    logger.error("Stale flight cleanup failed: %s", exc, exc_info=True)
                continue
            break

    async def _ensure_registry(
        self, drone_id: str, udp_port: Optional[int], sysid: Optional[int], last_seen_ts: int
    ) -> None:
        if udp_port is None:
            return
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(
                    text(
                        """
                        INSERT INTO drone_registry (
                            drone_id, assigned_udp_port, total_flights, last_seen_timestamp, serial_number, real_drone_id, created_at, updated_at
                        ) VALUES (
                            :drone_id, :assigned_udp_port, 0, :last_seen_ts, :serial_number, NULL, :now_ts, :now_ts
                        )
                        ON CONFLICT (drone_id) DO UPDATE
                        SET
                            assigned_udp_port = EXCLUDED.assigned_udp_port,
                            last_seen_timestamp = EXCLUDED.last_seen_timestamp,
                            serial_number = COALESCE(EXCLUDED.serial_number, drone_registry.serial_number),
                            updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {
                        "drone_id": drone_id,
                        "assigned_udp_port": int(udp_port),
                        "last_seen_ts": last_seen_ts,
                        "serial_number": str(sysid) if sysid is not None else None,
                        "now_ts": last_seen_ts,
                    },
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to upsert drone_registry for %s: %s", drone_id, exc)

    async def _start_flight(self, drone_id: str, udp_port: Optional[int], now_ts: float) -> None:
        start_ts = int(now_ts)
        flight_id = str(uuid.uuid4())
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    text("SELECT total_flights FROM drone_registry WHERE drone_id = :drone_id"),
                    {"drone_id": drone_id},
                )
                current = result.scalar_one_or_none() or 0
                flight_count = int(current) + 1

                await db.execute(
                    text(
                        """
                        INSERT INTO flights (
                            flight_id, drone_id, flight_count, start_timestamp
                        ) VALUES (
                            :flight_id, :drone_id, :flight_count, :start_ts
                        )
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {
                        "flight_id": flight_id,
                        "drone_id": drone_id,
                        "flight_count": flight_count,
                        "start_ts": start_ts,
                    },
                )

                await db.execute(
                    text(
                        """
                        UPDATE drone_registry
                        SET total_flights = :flight_count, last_seen_timestamp = :last_seen, updated_at = :last_seen
                        WHERE drone_id = :drone_id
                        """
                    ),
                    {"flight_count": flight_count, "last_seen": start_ts, "drone_id": drone_id},
                )

                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to start flight for %s: %s", drone_id, exc, exc_info=True)
                return

        async with self._lock:
            self._active[drone_id] = FlightState(
                flight_id=flight_id,
                drone_id=drone_id,
                flight_count=flight_count,
                start_ts=start_ts,
                last_heartbeat_ts=now_ts,
                last_telemetry_ts=now_ts,
                last_armed_state=True,
                last_state_change_ts=now_ts,
            )
        logger.info("Flight START: %s flight_id=%s flight_count=%s", drone_id, flight_id, flight_count)

    async def _close_flight(self, drone_id: str, now_ts: float, auto_closed: bool) -> None:
        async with self._lock:
            state = self._active.pop(drone_id, None)
        if not state:
            logger.debug("_close_flight called for %s but no active flight found", drone_id)
            return
        reason = "auto-closed" if auto_closed else "DISARM"
        logger.info("Flight END: %s flight_id=%s reason=%s", drone_id, state.flight_id, reason)
        await self._finalize_flight_state(state, end_ts=int(now_ts), auto_closed=auto_closed)
        async with self._lock:
            self._armed_state[drone_id] = False
            self._state_change_at[drone_id] = now_ts

    async def _finalize_flight_state(self, state: FlightState, end_ts: int, auto_closed: bool) -> None:
        duration = max(0, end_ts - int(state.start_ts))
        metrics = state.metrics
        summary = {
            "auto_closed": auto_closed,
            "start_timestamp": state.start_ts,
            "end_timestamp": end_ts,
            "duration_seconds": duration,
            "max_altitude_m": metrics.max_altitude_m,
            "max_speed_mps": metrics.max_speed_mps,
            "battery_start_pct": metrics.battery_start_pct,
            "battery_end_pct": metrics.battery_end_pct,
            "gps_issues_count": metrics.gps_issues_count,
            "emergency_events_count": metrics.emergency_events_count,
        }
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(
                    text(
                        """
                        UPDATE flights
                        SET
                            end_timestamp = :end_ts,
                            duration_seconds = :duration,
                            max_altitude_m = COALESCE(:max_altitude, max_altitude_m),
                            max_speed_mps = COALESCE(:max_speed, max_speed_mps),
                            battery_start_pct = COALESCE(:battery_start, battery_start_pct),
                            battery_end_pct = COALESCE(:battery_end, battery_end_pct),
                            gps_issues_count = COALESCE(:gps_issues, gps_issues_count),
                            emergency_events_count = COALESCE(:emergency_events, emergency_events_count),
                            summary_data = :summary
                        WHERE flight_id = :flight_id
                        """
                    ),
                    {
                        "end_ts": end_ts,
                        "duration": duration,
                        "max_altitude": metrics.max_altitude_m,
                        "max_speed": metrics.max_speed_mps,
                        "battery_start": metrics.battery_start_pct,
                        "battery_end": metrics.battery_end_pct,
                        "gps_issues": metrics.gps_issues_count,
                        "emergency_events": metrics.emergency_events_count,
                        "summary": summary,
                        "flight_id": state.flight_id,
                    },
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to finalize flight %s: %s", state.flight_id, exc, exc_info=True)
                return
        logger.info(
            "Flight end: %s flight_id=%s auto_closed=%s duration=%ss",
            state.drone_id,
            state.flight_id,
            auto_closed,
            duration,
        )

    async def _finalize_flight_by_id(
        self,
        flight_id: str,
        drone_id: str,
        flight_count: int,
        start_ts: int,
        end_ts: int,
        auto_closed: bool,
    ) -> None:
        await self._finalize_flight_state(
            FlightState(
                flight_id=flight_id,
                drone_id=drone_id,
                flight_count=flight_count,
                start_ts=start_ts,
                last_heartbeat_ts=time.time(),
                last_telemetry_ts=time.time(),
                last_armed_state=False,
                last_state_change_ts=time.time(),
            ),
            end_ts=end_ts,
            auto_closed=auto_closed,
        )

    async def _persist_flight_telemetry(self, flight_id: str, telemetry: NormalizedTelemetry) -> None:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text(
                        """
                        INSERT INTO flight_telemetry (
                            flight_id, timestamp, drone_id, latitude, longitude, altitude_m,
                            battery_pct, flight_mode, ground_speed_mps, climb_rate_mps, heading_deg,
                            gps_lost, is_emergency, ingest_timestamp
                        ) VALUES (
                            :flight_id, :timestamp, :drone_id, :latitude, :longitude, :altitude_m,
                            :battery_pct, :flight_mode, :ground_speed_mps, :climb_rate_mps, :heading_deg,
                            :gps_lost, :is_emergency, :ingest_ts
                        )
                        ON CONFLICT (flight_id, timestamp) DO NOTHING
                        """
                    ),
                    {
                        "flight_id": flight_id,
                        "timestamp": int(telemetry.source_timestamp),
                        "drone_id": telemetry.drone_id,
                        "latitude": telemetry.position.lat if telemetry.position else None,
                        "longitude": telemetry.position.lon if telemetry.position else None,
                        "altitude_m": telemetry.position.alt_m if telemetry.position else None,
                        "battery_pct": telemetry.battery_pct,
                        "flight_mode": telemetry.flight_mode,
                        "ground_speed_mps": telemetry.derived.ground_speed_mps,
                        "climb_rate_mps": telemetry.derived.climb_rate_mps,
                        "heading_deg": telemetry.derived.heading_deg,
                        "gps_lost": telemetry.flags.gps_lost,
                        "is_emergency": telemetry.flags.is_emergency,
                        "ingest_ts": telemetry.ingest_timestamp,
                    },
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist flight telemetry for %s: %s", telemetry.drone_id, exc)


_tracker: Optional[FlightTracker] = None


async def start_tracker() -> FlightTracker:
    global _tracker
    if _tracker is None:
        _tracker = FlightTracker()
    await _tracker.start()
    return _tracker


def get_tracker() -> Optional[FlightTracker]:
    return _tracker

