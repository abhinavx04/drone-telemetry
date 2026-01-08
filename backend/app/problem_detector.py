"""
Problem and anomaly detection from flight telemetry.
Identifies issues like battery problems, GPS loss, altitude anomalies, etc.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from app.flight_detector import TelemetryPoint

logger = logging.getLogger(__name__)


class ProblemSeverity(str, Enum):
    """Problem severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ProblemType(str, Enum):
    """Types of problems that can be detected."""

    LOW_BATTERY = "low_battery"
    CRITICAL_BATTERY = "critical_battery"
    RAPID_BATTERY_DRAIN = "rapid_battery_drain"
    GPS_LOSS = "gps_loss"
    GPS_POOR_SIGNAL = "gps_poor_signal"
    ALTITUDE_DROP = "altitude_drop"
    ALTITUDE_EXCEEDED = "altitude_exceeded"
    SPEED_ANOMALY = "speed_anomaly"
    EMERGENCY_MODE = "emergency_mode"
    RC_LOSS = "rc_loss"
    MODE_CHANGE_FREQUENT = "mode_change_frequent"


@dataclass
class Problem:
    """Detected problem/anomaly."""

    type: ProblemType
    severity: ProblemSeverity
    timestamp: int
    value: Optional[float] = None
    description: str = ""
    duration_seconds: Optional[int] = None
    start_timestamp: Optional[int] = None


class ProblemDetector:
    """Detects problems and anomalies in flight telemetry."""

    def __init__(
        self,
        low_battery_threshold: float = 20.0,
        critical_battery_threshold: float = 10.0,
        rapid_drain_rate_per_min: float = 2.0,
        gps_loss_duration_threshold_sec: int = 30,
        altitude_drop_threshold_m: float = 10.0,
        altitude_drop_duration_sec: int = 5,
        max_speed_threshold_mps: float = 50.0,
        min_speed_threshold_mps: float = 0.5,
    ):
        self.low_battery_threshold = low_battery_threshold
        self.critical_battery_threshold = critical_battery_threshold
        self.rapid_drain_rate = rapid_drain_rate_per_min
        self.gps_loss_threshold = gps_loss_duration_threshold_sec
        self.altitude_drop_threshold = altitude_drop_threshold_m
        self.altitude_drop_duration = altitude_drop_duration_sec
        self.max_speed_threshold = max_speed_threshold_mps
        self.min_speed_threshold = min_speed_threshold_mps

    def analyze_flight(
        self, points: List[TelemetryPoint]
    ) -> tuple[List[Problem], dict]:
        """
        Analyze flight telemetry for problems and calculate statistics.

        Returns:
            (problems, statistics)
        """
        if not points:
            return [], {}

        problems: List[Problem] = []
        problems.extend(self._detect_battery_issues(points))
        problems.extend(self._detect_gps_issues(points))
        problems.extend(self._detect_altitude_anomalies(points))
        problems.extend(self._detect_speed_anomalies(points))
        problems.extend(self._detect_emergency_events(points))
        problems.extend(self._detect_rc_loss(points))
        problems.extend(self._detect_mode_changes(points))

        statistics = self._calculate_statistics(points)

        return problems, statistics

    def _detect_battery_issues(self, points: List[TelemetryPoint]) -> List[Problem]:
        """Detect battery-related problems."""
        problems: List[Problem] = []
        last_battery: Optional[float] = None
        last_timestamp: Optional[int] = None

        for point in points:
            if point.battery_pct is None:
                continue

            # Low battery warning
            if point.battery_pct < self.critical_battery_threshold:
                problems.append(
                    Problem(
                        type=ProblemType.CRITICAL_BATTERY,
                        severity=ProblemSeverity.CRITICAL,
                        timestamp=point.timestamp,
                        value=point.battery_pct,
                        description=f"Battery critically low: {point.battery_pct:.1f}%",
                    )
                )
            elif point.battery_pct < self.low_battery_threshold:
                problems.append(
                    Problem(
                        type=ProblemType.LOW_BATTERY,
                        severity=ProblemSeverity.WARNING,
                        timestamp=point.timestamp,
                        value=point.battery_pct,
                        description=f"Battery low: {point.battery_pct:.1f}%",
                    )
                )

            # Rapid battery drain
            if last_battery is not None and last_timestamp is not None:
                time_diff_minutes = (point.timestamp - last_timestamp) / 60.0
                if time_diff_minutes > 0:
                    drain_rate = (last_battery - point.battery_pct) / time_diff_minutes
                    if drain_rate > self.rapid_drain_rate:
                        problems.append(
                            Problem(
                                type=ProblemType.RAPID_BATTERY_DRAIN,
                                severity=ProblemSeverity.WARNING,
                                timestamp=point.timestamp,
                                value=drain_rate,
                                description=f"Rapid battery drain: {drain_rate:.2f}% per minute",
                            )
                        )

            last_battery = point.battery_pct
            last_timestamp = point.timestamp

        return problems

    def _detect_gps_issues(self, points: List[TelemetryPoint]) -> List[Problem]:
        """Detect GPS-related problems."""
        problems: List[Problem] = []
        gps_loss_start: Optional[int] = None

        for point in points:
            is_gps_lost = point.gps_lost is True or (
                point.latitude is None and point.longitude is None
            )

            if is_gps_lost:
                if gps_loss_start is None:
                    gps_loss_start = point.timestamp
            else:
                if gps_loss_start is not None:
                    duration = point.timestamp - gps_loss_start
                    if duration >= self.gps_loss_threshold:
                        problems.append(
                            Problem(
                                type=ProblemType.GPS_LOSS,
                                severity=ProblemSeverity.ERROR,
                                timestamp=point.timestamp,
                                start_timestamp=gps_loss_start,
                                duration_seconds=duration,
                                description=f"GPS signal lost for {duration} seconds",
                            )
                        )
                    gps_loss_start = None

        # Check if GPS loss extends to end of flight
        if gps_loss_start is not None and points:
            duration = points[-1].timestamp - gps_loss_start
            if duration >= self.gps_loss_threshold:
                problems.append(
                    Problem(
                        type=ProblemType.GPS_LOSS,
                        severity=ProblemSeverity.ERROR,
                        timestamp=points[-1].timestamp,
                        start_timestamp=gps_loss_start,
                        duration_seconds=duration,
                        description=f"GPS signal lost for {duration} seconds (ongoing)",
                    )
                )

        return problems

    def _detect_altitude_anomalies(
        self, points: List[TelemetryPoint]
    ) -> List[Problem]:
        """Detect altitude-related problems."""
        problems: List[Problem] = []
        last_altitude: Optional[float] = None
        last_timestamp: Optional[int] = None
        drop_start_altitude: Optional[float] = None
        drop_start_timestamp: Optional[int] = None

        for point in points:
            if point.altitude_m is None:
                continue

            # Ground collision check
            if point.altitude_m < 0:
                problems.append(
                    Problem(
                        type=ProblemType.ALTITUDE_DROP,
                        severity=ProblemSeverity.CRITICAL,
                        timestamp=point.timestamp,
                        value=point.altitude_m,
                        description=f"Altitude below ground level: {point.altitude_m:.1f}m",
                    )
                )

            # Sudden altitude drop
            if last_altitude is not None and last_timestamp is not None:
                altitude_change = last_altitude - point.altitude_m
                time_diff = point.timestamp - last_timestamp

                if altitude_change > self.altitude_drop_threshold:
                    if drop_start_altitude is None:
                        drop_start_altitude = last_altitude
                        drop_start_timestamp = last_timestamp
                else:
                    if (
                        drop_start_altitude is not None
                        and drop_start_timestamp is not None
                        and time_diff <= self.altitude_drop_duration
                    ):
                        drop_amount = drop_start_altitude - point.altitude_m
                        problems.append(
                            Problem(
                                type=ProblemType.ALTITUDE_DROP,
                                severity=ProblemSeverity.WARNING,
                                timestamp=point.timestamp,
                                start_timestamp=drop_start_timestamp,
                                value=drop_amount,
                                duration_seconds=time_diff,
                                description=f"Sudden altitude drop: {drop_amount:.1f}m in {time_diff}s",
                            )
                        )
                    drop_start_altitude = None
                    drop_start_timestamp = None

            last_altitude = point.altitude_m
            last_timestamp = point.timestamp

        return problems

    def _detect_speed_anomalies(self, points: List[TelemetryPoint]) -> List[Problem]:
        """Detect speed-related problems."""
        problems: List[Problem] = []

        for point in points:
            if point.ground_speed_mps is None:
                continue

            # Too fast
            if point.ground_speed_mps > self.max_speed_threshold:
                problems.append(
                    Problem(
                        type=ProblemType.SPEED_ANOMALY,
                        severity=ProblemSeverity.WARNING,
                        timestamp=point.timestamp,
                        value=point.ground_speed_mps,
                        description=f"Speed exceeds threshold: {point.ground_speed_mps:.1f} m/s",
                    )
                )

        return problems

    def _detect_emergency_events(
        self, points: List[TelemetryPoint]
    ) -> List[Problem]:
        """Detect emergency mode activations."""
        problems: List[Problem] = []
        emergency_start: Optional[int] = None

        for point in points:
            if point.is_emergency:
                if emergency_start is None:
                    emergency_start = point.timestamp
            else:
                if emergency_start is not None:
                    duration = point.timestamp - emergency_start
                    problems.append(
                        Problem(
                            type=ProblemType.EMERGENCY_MODE,
                            severity=ProblemSeverity.CRITICAL,
                            timestamp=point.timestamp,
                            start_timestamp=emergency_start,
                            duration_seconds=duration,
                            description=f"Emergency mode activated for {duration} seconds",
                        )
                    )
                    emergency_start = None

        # Check if emergency extends to end
        if emergency_start is not None and points:
            duration = points[-1].timestamp - emergency_start
            problems.append(
                Problem(
                    type=ProblemType.EMERGENCY_MODE,
                    severity=ProblemSeverity.CRITICAL,
                    timestamp=points[-1].timestamp,
                    start_timestamp=emergency_start,
                    duration_seconds=duration,
                    description=f"Emergency mode activated for {duration} seconds (ongoing)",
                )
            )

        return problems

    def _detect_rc_loss(self, points: List[TelemetryPoint]) -> List[Problem]:
        """Detect RC (remote control) signal loss."""
        # RC loss detection would require rc_lost field in telemetry
        # For now, return empty list as TelemetryPoint doesn't have this field
        # Can be extended when rc_lost data is available
        return []

    def _detect_mode_changes(self, points: List[TelemetryPoint]) -> List[Problem]:
        """Detect frequent flight mode changes (could indicate problems)."""
        problems: List[Problem] = []
        mode_changes = 0
        last_mode: Optional[str] = None

        for point in points:
            if point.flight_mode and point.flight_mode != last_mode:
                if last_mode is not None:  # Don't count first mode
                    mode_changes += 1
                last_mode = point.flight_mode

        # Flag if too many mode changes in single flight
        if mode_changes > 10:  # Threshold
            problems.append(
                Problem(
                    type=ProblemType.MODE_CHANGE_FREQUENT,
                    severity=ProblemSeverity.WARNING,
                    timestamp=points[-1].timestamp if points else 0,
                    value=float(mode_changes),
                    description=f"Frequent mode changes detected: {mode_changes} changes",
                )
            )

        return problems

    def _calculate_statistics(self, points: List[TelemetryPoint]) -> dict:
        """Calculate flight statistics."""
        if not points:
            return {}

        stats: dict = {}

        # Speed statistics
        speeds = [p.ground_speed_mps for p in points if p.ground_speed_mps is not None]
        if speeds:
            stats["avg_speed_mps"] = sum(speeds) / len(speeds)
            stats["max_speed_mps"] = max(speeds)
            stats["min_speed_mps"] = min(speeds)

        # Altitude statistics
        altitudes = [p.altitude_m for p in points if p.altitude_m is not None]
        if altitudes:
            stats["avg_altitude_m"] = sum(altitudes) / len(altitudes)
            stats["max_altitude_m"] = max(altitudes)
            stats["min_altitude_m"] = min(altitudes)

        # Battery statistics
        batteries = [p.battery_pct for p in points if p.battery_pct is not None]
        if batteries:
            stats["battery_start_pct"] = batteries[0]
            stats["battery_end_pct"] = batteries[-1]
            stats["battery_min_pct"] = min(batteries)
            stats["battery_drain_pct"] = batteries[0] - batteries[-1]

        # Distance traveled
        positions = [
            (p.latitude, p.longitude)
            for p in points
            if p.latitude is not None and p.longitude is not None
        ]
        if len(positions) > 1:
            total_distance = 0.0
            for i in range(1, len(positions)):
                dist = self._haversine_distance(
                    positions[i - 1][0],
                    positions[i - 1][1],
                    positions[i][0],
                    positions[i][1],
                )
                total_distance += dist
            stats["distance_traveled_m"] = total_distance

        # Flight mode changes
        modes = set(p.flight_mode for p in points if p.flight_mode)
        stats["flight_mode_changes"] = len(modes)
        stats["modes_used"] = list(modes)

        # GPS quality
        gps_lost_count = sum(1 for p in points if p.gps_lost is True)
        stats["gps_lost_points"] = gps_lost_count
        stats["gps_lost_percentage"] = (
            (gps_lost_count / len(points) * 100) if points else 0.0
        )

        # Emergency events
        emergency_count = sum(1 for p in points if p.is_emergency is True)
        stats["emergency_points"] = emergency_count

        return stats

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates in meters."""
        from math import asin, cos, radians, sin, sqrt

        R = 6371000  # Earth radius in meters
        phi1 = radians(lat1)
        phi2 = radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)

        a = (
            sin(delta_phi / 2) ** 2
            + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
        )
        c = 2 * asin(sqrt(a))

        return R * c

