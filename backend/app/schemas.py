from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Union, List, Optional
import logging

logger = logging.getLogger(__name__)

class TelemetryIn(BaseModel):
    drone_id: str = Field(..., max_length=50)
    latitude: float
    longitude: float
    absolute_altitude_m: float | None = None
    timestamp: Union[datetime, int]
    battery_percentage: Optional[float] = None
    flight_mode: Optional[str] = None
    is_online: Optional[bool] = True
    flight_count: Optional[int] = 0
    emergency_status: Optional[bool] = False
    emergency_reasons: Optional[List[str]] = None
    trajectory: Optional[List[dict]] = None

    @validator('timestamp')
    def convert_timestamp(cls, v):
        try:
            if isinstance(v, datetime):
                logger.debug(f"Converting datetime {v} to Unix timestamp")
                return int(v.timestamp())
            elif isinstance(v, int):
                logger.debug(f"Using integer timestamp: {v}")
                return v
            elif isinstance(v, str):
                # Try to parse string as datetime
                try:
                    dt = datetime.fromisoformat(v)
                    logger.debug(f"Converting string datetime {v} to Unix timestamp")
                    return int(dt.timestamp())
                except ValueError:
                    # Try to parse as integer
                    try:
                        ts = int(v)
                        logger.debug(f"Converting string {v} to integer timestamp")
                        return ts
                    except ValueError:
                        raise ValueError(f'Invalid timestamp string: {v}')
            else:
                raise ValueError(f'Timestamp must be datetime, integer, or ISO format string, got {type(v)}')
        except Exception as e:
            logger.error(f"Timestamp conversion error: {e}")
            raise ValueError(f"Failed to convert timestamp: {e}")

    @validator('flight_mode')
    def validate_flight_mode(cls, v):
        if v is not None and v not in ['manual', 'atti', 'rth']:
            raise ValueError('Flight mode must be one of: manual, atti, rth')
        return v

    @validator('emergency_reasons')
    def validate_emergency_reasons(cls, v):
        if v is not None:
            valid_reasons = {'low_battery', 'gps_loss', 'system_failure', 'loss_of_control', 'obstacle_detected'}
            invalid_reasons = set(v) - valid_reasons
            if invalid_reasons:
                raise ValueError(f'Invalid emergency reasons: {invalid_reasons}')
        return v

class TelemetryOut(TelemetryIn):
    id: int