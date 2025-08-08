from sqlalchemy import Column, Integer, String, Float, BigInteger, Boolean, JSON, ARRAY
from app.db import Base

class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String(50), index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    absolute_altitude_m = Column(Float, nullable=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    battery_percentage = Column(Float, nullable=True)
    flight_mode = Column(String(50), nullable=True)  # manual, atti, rth
    is_online = Column(Boolean, default=True)
    flight_count = Column(Integer, default=0)
    emergency_status = Column(Boolean, default=False)
    emergency_reasons = Column(ARRAY(String), nullable=True)  # Store array of emergency reasons
    trajectory = Column(JSON, nullable=True)  # Store array of lat/long points for area covered