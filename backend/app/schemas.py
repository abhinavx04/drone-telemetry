from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class TelemetryIn(BaseModel):
    """
    Raw telemetry payload accepted from MQTT. Extra fields are ignored so we
    can ingest richer upstream data without breaking validation.
    """

    model_config = ConfigDict(extra="ignore")

    drone_id: str = Field(..., max_length=50)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    absolute_altitude_m: Optional[float] = None
    timestamp: Optional[int | datetime | str] = None
    battery_percentage: Optional[float] = None
    flight_mode: Optional[str] = None
    is_online: Optional[bool] = True
    rc_lost: Optional[bool] = None
    gps_fix: Optional[bool] = None
    is_emergency: Optional[bool] = None
    ground_speed_mps: Optional[float] = None
    climb_rate_mps: Optional[float] = None
    heading_deg: Optional[float] = None
    ingest_source: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def convert_timestamp(cls, v):
        if v is None:
            return None
        try:
            if isinstance(v, datetime):
                return int(v.timestamp())
            if isinstance(v, (int, float)):
                return int(v)
            if isinstance(v, str):
                try:
                    dt = datetime.fromisoformat(v)
                    return int(dt.timestamp())
                except ValueError:
                    return int(v)
            raise ValueError(f"Unsupported timestamp type: {type(v)}")
        except Exception as exc:  # noqa: BLE001
            logger.error("Timestamp conversion error: %s", exc)
            raise ValueError(f"Failed to convert timestamp: {exc}") from exc


class Position(BaseModel):
    lat: float
    lon: float
    alt_m: Optional[float] = None


class TelemetryFlags(BaseModel):
    gps_lost: bool = False
    rc_lost: Optional[bool] = None
    is_emergency: bool = False


class TelemetryDerived(BaseModel):
    ground_speed_mps: Optional[float] = None
    climb_rate_mps: Optional[float] = None
    heading_deg: Optional[float] = None


class NormalizedTelemetry(BaseModel):
    """
    Sanitized telemetry the API layer will expose.
    """

    model_config = ConfigDict(extra="forbid")

    drone_id: str
    source_timestamp: int
    ingest_timestamp: float
    position: Optional[Position] = None
    battery_pct: Optional[float] = None
    flight_mode: Optional[str] = None
    flags: TelemetryFlags
    derived: TelemetryDerived


class BatteryOut(BaseModel):
    pct: Optional[float]
    voltage_v: Optional[float] = None


class DroneSummary(BaseModel):
    id: str
    status: Literal["online", "stale", "offline"]
    last_seen_ts: Optional[int]
    battery_pct: Optional[float]
    flight_mode: Optional[str]
    position: Optional[Position]


class TelemetryLatestOut(BaseModel):
    id: str
    status: Literal["online", "stale", "offline"]
    last_seen_ts: Optional[int]
    source_timestamp: Optional[int]
    position: Optional[Position]
    battery: BatteryOut
    flight_mode: Optional[str]
    flags: TelemetryFlags
    derived: TelemetryDerived
    version: int


class HealthResponse(BaseModel):
    status: str
    mqtt: dict
    uptime_s: int


class TelemetryOut(TelemetryIn):
    """Kept for compatibility with the historic DB-backed endpoints."""
    pass