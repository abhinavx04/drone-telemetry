"""
Flight detection from telemetry data.
Detects flight boundaries when ARM/DISARM events are not available.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TelemetryPoint:
    """Raw telemetry point from imported data."""

    timestamp: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    battery_pct: Optional[float] = None
    flight_mode: Optional[str] = None
    ground_speed_mps: Optional[float] = None
    climb_rate_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    gps_lost: Optional[bool] = None
    is_emergency: Optional[bool] = None


@dataclass
class FlightBoundary:
    """Detected flight boundary from telemetry."""

    start_index: int  # Index in telemetry points array
    end_index: int  # Index in telemetry points array (inclusive)
    start_timestamp: int
    end_timestamp: int
    confidence: float  # 0.0 to 1.0


class FlightDetector:
    """Detects flight boundaries from telemetry patterns."""

    def __init__(
        self,
        time_gap_threshold_sec: int = 300,  # 5 minutes
        altitude_threshold_m: float = 5.0,  # 5 meters
        min_flight_duration_sec: int = 10,  # Minimum 10 seconds
        speed_threshold_mps: float = 1.0,  # 1 m/s minimum movement
    ):
        self.time_gap_threshold = time_gap_threshold_sec
        self.altitude_threshold = altitude_threshold_m
        self.min_flight_duration = min_flight_duration_sec
        self.speed_threshold = speed_threshold_mps

    def detect_flights(self, points: List[TelemetryPoint]) -> List[FlightBoundary]:
        """
        Detect flight boundaries from telemetry points.

        Algorithm:
        1. Identify takeoff: altitude increase OR movement from stationary
        2. Identify landing: altitude decrease OR movement to stationary
        3. Use time gaps as flight separators
        4. Filter out too-short "flights" (likely false positives)
        """
        if len(points) < 2:
            return []

        flights: List[FlightBoundary] = []
        current_flight_start: Optional[int] = None
        last_timestamp: Optional[int] = None
        last_altitude: Optional[float] = None
        last_latitude: Optional[float] = None
        last_longitude: Optional[float] = None

        for i, point in enumerate(points):
            # Initialize tracking variables on first point
            if last_timestamp is None:
                current_flight_start = i
                last_timestamp = point.timestamp
                last_altitude = point.altitude_m
                last_latitude = point.latitude
                last_longitude = point.longitude
                continue

            # Check for time gap (new flight)
            time_gap = point.timestamp - last_timestamp
            if time_gap > self.time_gap_threshold and current_flight_start is not None:
                # Close previous flight
                flight = self._finalize_flight(
                    points, current_flight_start, i - 1, flights
                )
                if flight:
                    flights.append(flight)
                # Start new flight
                current_flight_start = i

            # Check for takeoff (if we don't have a flight started)
            if current_flight_start is None:
                if self._is_takeoff(point, last_altitude, last_latitude, last_longitude):
                    current_flight_start = i

            # Check for landing (if we have a flight in progress)
            elif current_flight_start is not None:
                if self._is_landing(
                    point, last_altitude, last_latitude, last_longitude, points, i
                ):
                    # Close flight
                    flight = self._finalize_flight(
                        points, current_flight_start, i, flights
                    )
                    if flight:
                        flights.append(flight)
                    current_flight_start = None

            # Update tracking variables
            last_timestamp = point.timestamp
            last_altitude = point.altitude_m
            last_latitude = point.latitude
            last_longitude = point.longitude

        # Close any open flight at the end
        if current_flight_start is not None:
            flight = self._finalize_flight(
                points, current_flight_start, len(points) - 1, flights
            )
            if flight:
                flights.append(flight)

        return flights

    def _is_takeoff(
        self,
        point: TelemetryPoint,
        last_altitude: Optional[float],
        last_latitude: Optional[float],
        last_longitude: Optional[float],
    ) -> bool:
        """Detect if this point represents a takeoff."""
        # Altitude-based takeoff detection
        if (
            last_altitude is not None
            and point.altitude_m is not None
            and point.altitude_m - last_altitude > self.altitude_threshold
        ):
            return True

        # Movement-based takeoff detection
        if (
            last_latitude is not None
            and last_longitude is not None
            and point.latitude is not None
            and point.longitude is not None
        ):
            distance = self._haversine_distance(
                last_latitude, last_longitude, point.latitude, point.longitude
            )
            # If moved more than ~5 meters, likely takeoff
            if distance > 5.0:
                return True

        # Speed-based takeoff detection
        if (
            point.ground_speed_mps is not None
            and point.ground_speed_mps > self.speed_threshold
        ):
            return True

        return False

    def _is_landing(
        self,
        point: TelemetryPoint,
        last_altitude: Optional[float],
        last_latitude: Optional[float],
        last_longitude: Optional[float],
        points: List[TelemetryPoint],
        current_index: int,
    ) -> bool:
        """Detect if this point represents a landing."""
        # Check if altitude dropped significantly
        if (
            last_altitude is not None
            and point.altitude_m is not None
            and last_altitude - point.altitude_m > self.altitude_threshold
            and point.altitude_m < self.altitude_threshold
        ):
            # Check if we stay low for a bit (landing confirmation)
            lookahead = min(5, len(points) - current_index - 1)
            if lookahead > 0:
                future_altitudes = [
                    p.altitude_m
                    for p in points[current_index + 1 : current_index + 1 + lookahead]
                    if p.altitude_m is not None
                ]
                if future_altitudes and all(a < self.altitude_threshold for a in future_altitudes):
                    return True

        # Check if movement stopped
        if (
            last_latitude is not None
            and last_longitude is not None
            and point.latitude is not None
            and point.longitude is not None
        ):
            distance = self._haversine_distance(
                last_latitude, last_longitude, point.latitude, point.longitude
            )
            # If moved less than 1 meter, likely landing
            if distance < 1.0 and point.ground_speed_mps is not None and point.ground_speed_mps < 0.5:
                return True

        return False

    def _finalize_flight(
        self,
        points: List[TelemetryPoint],
        start_index: int,
        end_index: int,
        existing_flights: List[FlightBoundary],
    ) -> Optional[FlightBoundary]:
        """Create flight boundary if valid."""
        if start_index >= end_index:
            return None

        start_point = points[start_index]
        end_point = points[end_index]

        # Check minimum duration
        duration = end_point.timestamp - start_point.timestamp
        if duration < self.min_flight_duration:
            logger.debug(
                "Skipping flight candidate: duration %ds < minimum %ds",
                duration,
                self.min_flight_duration,
            )
            return None

        # Calculate confidence based on various factors
        confidence = self._calculate_confidence(points, start_index, end_index)

        return FlightBoundary(
            start_index=start_index,
            end_index=end_index,
            start_timestamp=start_point.timestamp,
            end_timestamp=end_point.timestamp,
            confidence=confidence,
        )

    def _calculate_confidence(
        self, points: List[TelemetryPoint], start_index: int, end_index: int
    ) -> float:
        """Calculate confidence score for detected flight (0.0 to 1.0)."""
        flight_points = points[start_index : end_index + 1]

        confidence = 0.5  # Base confidence

        # Altitude change increases confidence
        altitudes = [p.altitude_m for p in flight_points if p.altitude_m is not None]
        if altitudes:
            altitude_change = max(altitudes) - min(altitudes)
            if altitude_change > 10:
                confidence += 0.2
            elif altitude_change > 5:
                confidence += 0.1

        # Movement increases confidence
        positions = [
            (p.latitude, p.longitude)
            for p in flight_points
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
            if total_distance > 100:  # More than 100 meters traveled
                confidence += 0.2
            elif total_distance > 50:
                confidence += 0.1

        # Duration increases confidence
        duration = points[end_index].timestamp - points[start_index].timestamp
        if duration > 300:  # More than 5 minutes
            confidence += 0.1

        return min(1.0, confidence)

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

