"""
Historical telemetry import processor.
Handles bulk telemetry imports, flight detection, and problem analysis.
"""

from __future__ import annotations

import csv
import json
import logging
import time
import uuid
from dataclasses import dataclass
from io import StringIO
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.flight_detector import FlightBoundary, FlightDetector, TelemetryPoint
from app.problem_detector import Problem, ProblemDetector

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of telemetry import operation."""

    flights_created: int
    telemetry_points_imported: int
    problems_detected: int
    flight_ids: List[str]
    warnings: List[str]
    errors: List[str]


class TelemetryImporter:
    """Processes and imports historical telemetry data."""

    def __init__(self):
        self.flight_detector = FlightDetector()
        self.problem_detector = ProblemDetector()

    async def import_from_file(
        self,
        drone_id: str,
        file_content: bytes,
        filename: str,
        gcs_flight_count_offset: Optional[int] = None,
    ) -> ImportResult:
        """
        Import telemetry from uploaded file (CSV or JSON).

        Args:
            drone_id: Drone identifier
            file_content: File content bytes
            filename: Original filename
            gcs_flight_count_offset: Optional offset for flight count numbering

        Returns:
            ImportResult with details of import
        """
        try:
            # Parse file based on extension
            if filename.endswith(".json"):
                points = self._parse_json(file_content)
            elif filename.endswith(".csv"):
                points = self._parse_csv(file_content)
            else:
                # Try to auto-detect format
                try:
                    points = self._parse_json(file_content)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    points = self._parse_csv(file_content)

            if not points:
                raise ValueError("No telemetry points found in file")

            # Sort by timestamp
            points.sort(key=lambda p: p.timestamp)

            # Import telemetry
            return await self.import_telemetry(
                drone_id, points, gcs_flight_count_offset
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to import telemetry from file: %s", exc, exc_info=True)
            raise ValueError(f"Import failed: {exc}") from exc

    def _parse_json(self, content: bytes) -> List[TelemetryPoint]:
        """Parse JSON telemetry data."""
        try:
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, list):
                return [self._point_from_dict(item) for item in data]
            elif isinstance(data, dict) and "telemetry" in data:
                return [self._point_from_dict(item) for item in data["telemetry"]]
            else:
                raise ValueError("Invalid JSON format: expected array or object with 'telemetry' key")
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

    def _parse_csv(self, content: bytes) -> List[TelemetryPoint]:
        """Parse CSV telemetry data."""
        try:
            text_content = content.decode("utf-8")
            reader = csv.DictReader(StringIO(text_content))
            points = []
            for row in reader:
                point = self._point_from_dict(row)
                if point.timestamp:  # Only add if timestamp is present
                    points.append(point)
            return points
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid CSV: {exc}") from exc

    def _point_from_dict(self, data: dict) -> TelemetryPoint:
        """Convert dict to TelemetryPoint."""
        # Handle timestamp conversion
        timestamp = data.get("timestamp")
        if timestamp:
            if isinstance(timestamp, str):
                # Try ISO format
                try:
                    from datetime import datetime

                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = int(dt.timestamp())
                except (ValueError, AttributeError):
                    # Try parsing as Unix timestamp string
                    try:
                        timestamp = int(float(timestamp))
                    except (ValueError, TypeError):
                        timestamp = None
            elif isinstance(timestamp, (int, float)):
                timestamp = int(timestamp)
            else:
                timestamp = None

        return TelemetryPoint(
            timestamp=timestamp or 0,
            latitude=self._float_or_none(data.get("latitude")),
            longitude=self._float_or_none(data.get("longitude")),
            altitude_m=self._float_or_none(data.get("altitude_m", data.get("altitude"))),
            battery_pct=self._float_or_none(
                data.get("battery_pct", data.get("battery_percentage", data.get("battery")))
            ),
            flight_mode=data.get("flight_mode", data.get("mode")),
            ground_speed_mps=self._float_or_none(
                data.get("ground_speed_mps", data.get("speed"))
            ),
            climb_rate_mps=self._float_or_none(
                data.get("climb_rate_mps", data.get("climb_rate"))
            ),
            heading_deg=self._float_or_none(
                data.get("heading_deg", data.get("heading"))
            ),
            gps_lost=self._bool_or_none(
                data.get("gps_lost", data.get("gps_fix"))  # Note: gps_fix inverted
            ),
            is_emergency=self._bool_or_none(
                data.get("is_emergency", data.get("emergency"))
            ),
        )

    @staticmethod
    def _float_or_none(value) -> Optional[float]:
        """Convert value to float or None."""
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _bool_or_none(value) -> Optional[bool]:
        """Convert value to bool or None."""
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        if isinstance(value, (int, float)):
            return bool(value)
        return None

    async def import_telemetry(
        self,
        drone_id: str,
        points: List[TelemetryPoint],
        gcs_flight_count_offset: Optional[int] = None,
    ) -> ImportResult:
        """
        Import telemetry points, detect flights, and analyze problems.

        Args:
            drone_id: Drone identifier
            points: List of telemetry points
            gcs_flight_count_offset: Optional offset for flight count

        Returns:
            ImportResult
        """
        if not points:
            return ImportResult(
                flights_created=0,
                telemetry_points_imported=0,
                problems_detected=0,
                flight_ids=[],
                warnings=["No telemetry points provided"],
                errors=[],
            )

        # Ensure drone exists in registry
        await self._ensure_drone_registry(drone_id)

        # Detect flights
        logger.info("Detecting flights from %d telemetry points", len(points))
        flight_boundaries = self.flight_detector.detect_flights(points)
        logger.info("Detected %d flights", len(flight_boundaries))

        if not flight_boundaries:
            return ImportResult(
                flights_created=0,
                telemetry_points_imported=0,
                problems_detected=0,
                flight_ids=[],
                warnings=["No flights detected in telemetry data"],
                errors=[],
            )

        # Get current flight count for drone
        current_flight_count = await self._get_drone_flight_count(drone_id)

        # Import each flight
        flight_ids = []
        total_points_imported = 0
        total_problems = 0
        warnings = []
        errors = []

        for i, boundary in enumerate(flight_boundaries):
            try:
                # Calculate flight count
                if gcs_flight_count_offset is not None:
                    flight_count = gcs_flight_count_offset + i
                else:
                    flight_count = current_flight_count + i + 1

                # Extract flight telemetry
                flight_points = points[boundary.start_index : boundary.end_index + 1]

                # Analyze problems
                problems, statistics = self.problem_detector.analyze_flight(flight_points)
                total_problems += len(problems)

                # Create flight record
                flight_id = await self._create_flight(
                    drone_id,
                    flight_count,
                    boundary,
                    flight_points,
                    problems,
                    statistics,
                )

                # Import telemetry points
                points_imported = await self._bulk_import_telemetry(
                    flight_id, drone_id, flight_points
                )
                total_points_imported += points_imported
                flight_ids.append(flight_id)

                logger.info(
                    "Imported flight %s: %d points, %d problems",
                    flight_id,
                    points_imported,
                    len(problems),
                )

            except Exception as exc:  # noqa: BLE001
                error_msg = f"Failed to import flight {i+1}: {exc}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        # Update drone registry
        await self._update_drone_flight_count(
            drone_id, current_flight_count + len(flight_boundaries)
        )

        return ImportResult(
            flights_created=len(flight_ids),
            telemetry_points_imported=total_points_imported,
            problems_detected=total_problems,
            flight_ids=flight_ids,
            warnings=warnings,
            errors=errors,
        )

    async def _ensure_drone_registry(self, drone_id: str) -> None:
        """Ensure drone exists in registry."""
        async with AsyncSessionLocal() as db:
            try:
                # Extract UDP port from drone_id if format is "udp:PORT"
                udp_port = None
                if drone_id.startswith("udp:"):
                    try:
                        udp_port = int(drone_id.split(":")[1])
                    except (ValueError, IndexError):
                        pass

                await db.execute(
                    text(
                        """
                        INSERT INTO drone_registry (
                            drone_id, assigned_udp_port, total_flights, last_seen_timestamp,
                            created_at, updated_at
                        ) VALUES (
                            :drone_id, :udp_port, 0, :now_ts, :now_ts, :now_ts
                        )
                        ON CONFLICT (drone_id) DO NOTHING
                        """
                    ),
                    {
                        "drone_id": drone_id,
                        "udp_port": udp_port or 0,
                        "now_ts": int(time.time()),
                    },
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to ensure drone registry: %s", exc)

    async def _get_drone_flight_count(self, drone_id: str) -> int:
        """Get current flight count for drone."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "SELECT COALESCE(MAX(flight_count), 0) as max_count FROM flights WHERE drone_id = :drone_id"
                ),
                {"drone_id": drone_id},
            )
            row = result.mappings().first()
            return int(row["max_count"] if row else 0)

    async def _create_flight(
        self,
        drone_id: str,
        flight_count: int,
        boundary: FlightBoundary,
        points: List[TelemetryPoint],
        problems: List[Problem],
        statistics: dict,
    ) -> str:
        """Create flight record in database."""
        flight_id = str(uuid.uuid4())
        start_ts = boundary.start_timestamp
        end_ts = boundary.end_timestamp
        duration = end_ts - start_ts if end_ts else None

        # Calculate metrics
        altitudes = [p.altitude_m for p in points if p.altitude_m is not None]
        speeds = [p.ground_speed_mps for p in points if p.ground_speed_mps is not None]
        batteries = [p.battery_pct for p in points if p.battery_pct is not None]

        max_altitude = max(altitudes) if altitudes else None
        max_speed = max(speeds) if speeds else None
        battery_start = batteries[0] if batteries else None
        battery_end = batteries[-1] if batteries else None

        gps_issues = sum(1 for p in points if p.gps_lost is True)
        emergency_events = sum(1 for p in points if p.is_emergency is True)

        # Prepare summary_data
        summary_data = {
            "problems": [
                {
                    "type": p.type.value,
                    "severity": p.severity.value,
                    "timestamp": p.timestamp,
                    "value": p.value,
                    "description": p.description,
                    "duration_seconds": p.duration_seconds,
                    "start_timestamp": p.start_timestamp,
                }
                for p in problems
            ],
            "statistics": statistics,
            "detection_confidence": boundary.confidence,
        }

        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    """
                    INSERT INTO flights (
                        flight_id, drone_id, flight_count, start_timestamp, end_timestamp,
                        duration_seconds, max_altitude_m, max_speed_mps,
                        battery_start_pct, battery_end_pct,
                        gps_issues_count, emergency_events_count, summary_data
                    ) VALUES (
                        :flight_id, :drone_id, :flight_count, :start_ts, :end_ts,
                        :duration, :max_alt, :max_speed,
                        :battery_start, :battery_end,
                        :gps_issues, :emergency_events, :summary
                    )
                    """
                ),
                {
                    "flight_id": flight_id,
                    "drone_id": drone_id,
                    "flight_count": flight_count,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "duration": duration,
                    "max_alt": max_altitude,
                    "max_speed": max_speed,
                    "battery_start": battery_start,
                    "battery_end": battery_end,
                    "gps_issues": gps_issues,
                    "emergency_events": emergency_events,
                    "summary": json.dumps(summary_data),
                },
            )
            await db.commit()

        return flight_id

    async def _bulk_import_telemetry(
        self, flight_id: str, drone_id: str, points: List[TelemetryPoint]
    ) -> int:
        """Bulk import telemetry points for a flight."""
        if not points:
            return 0

        async with AsyncSessionLocal() as db:
            # Use batch insert for efficiency
            batch_size = 500
            imported = 0

            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                values = []
                for point in batch:
                    values.append(
                        {
                            "flight_id": flight_id,
                            "timestamp": point.timestamp,
                            "drone_id": drone_id,
                            "latitude": point.latitude,
                            "longitude": point.longitude,
                            "altitude_m": point.altitude_m,
                            "battery_pct": point.battery_pct,
                            "flight_mode": point.flight_mode,
                            "ground_speed_mps": point.ground_speed_mps,
                            "climb_rate_mps": point.climb_rate_mps,
                            "heading_deg": point.heading_deg,
                            "gps_lost": point.gps_lost,
                            "is_emergency": point.is_emergency,
                            "ingest_timestamp": None,
                        }
                    )

                # Batch insert using executemany
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
                            :gps_lost, :is_emergency, :ingest_timestamp
                        )
                        ON CONFLICT (flight_id, timestamp) DO NOTHING
                        """
                    ),
                    values,
                )
                imported += len(batch)

            await db.commit()

        return imported

    async def _update_drone_flight_count(self, drone_id: str, new_count: int) -> None:
        """Update drone registry with new flight count."""
        async with AsyncSessionLocal() as db:
            try:
                await db.execute(
                    text(
                        """
                        UPDATE drone_registry
                        SET total_flights = :count, updated_at = :now_ts
                        WHERE drone_id = :drone_id
                        """
                    ),
                    {"count": new_count, "drone_id": drone_id, "now_ts": int(time.time())},
                )
                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to update drone flight count: %s", exc)



