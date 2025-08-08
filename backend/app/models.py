from sqlalchemy import Column, String, Float, BigInteger, Boolean
from app.db import Base

class Telemetry(Base):
    __tablename__ = "telemetry"

    drone_id = Column(String(50), primary_key=True, nullable=False)
    timestamp = Column(BigInteger, primary_key=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    absolute_altitude_m = Column(Float, nullable=True)
    battery_percentage = Column(Float, nullable=True)
    flight_mode = Column(String(50), nullable=True)  # manual, atti, rth
    is_online = Column(Boolean, default=True)