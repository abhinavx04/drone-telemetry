from pydantic import BaseModel, Field

class TelemetryIn(BaseModel):
    drone_id: str = Field(..., max_length=50)
    latitude: float
    longitude: float
    absolute_altitude_m: float | None = None
    timestamp: int

class TelemetryOut(TelemetryIn):
    id: int