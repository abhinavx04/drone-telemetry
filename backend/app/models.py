from sqlalchemy import Column, Integer, String, Float, BigInteger
from app.db import Base

class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(String(50), index=True, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    absolute_altitude_m = Column(Float, nullable=True)
    timestamp = Column(BigInteger, nullable=False, index=True)