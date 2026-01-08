import time

from sqlalchemy import BigInteger, Boolean, Column, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

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
    rc_lost = Column(Boolean, nullable=True)
    gps_fix = Column(Boolean, nullable=True)  # True = GPS fix available, False/None = GPS lost
    is_emergency = Column(Boolean, nullable=True)


class DroneRegistry(Base):
    __tablename__ = "drone_registry"

    drone_id = Column(String(50), primary_key=True, nullable=False)
    assigned_udp_port = Column(Integer, unique=True, nullable=False)
    total_flights = Column(Integer, default=0, nullable=False)
    last_seen_timestamp = Column(BigInteger, nullable=True)
    serial_number = Column(String(50), nullable=True)  # stores MAVLink sysid when available
    real_drone_id = Column(String(100), nullable=True)
    created_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)
    updated_at = Column(BigInteger, default=lambda: int(time.time()), nullable=False)


class Flight(Base):
    __tablename__ = "flights"

    flight_id = Column(String(64), primary_key=True, nullable=False)
    drone_id = Column(String(50), nullable=False)
    flight_count = Column(Integer, nullable=False)
    start_timestamp = Column(BigInteger, nullable=False)
    end_timestamp = Column(BigInteger, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    max_altitude_m = Column(Float, nullable=True)
    max_speed_mps = Column(Float, nullable=True)
    battery_start_pct = Column(Float, nullable=True)
    battery_end_pct = Column(Float, nullable=True)
    gps_issues_count = Column(Integer, nullable=False, default=0)
    emergency_events_count = Column(Integer, nullable=False, default=0)
    summary_data = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("drone_id", "flight_count", name="uq_flights_drone_flight_count"),
        Index("idx_flights_drone", "drone_id"),
        Index("idx_flights_start_ts", "start_timestamp"),
    )


class FlightTelemetry(Base):
    __tablename__ = "flight_telemetry"

    flight_id = Column(String(64), primary_key=True, nullable=False)
    timestamp = Column(BigInteger, primary_key=True, nullable=False)
    drone_id = Column(String(50), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude_m = Column(Float, nullable=True)
    battery_pct = Column(Float, nullable=True)
    flight_mode = Column(String(50), nullable=True)
    ground_speed_mps = Column(Float, nullable=True)
    climb_rate_mps = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    gps_lost = Column(Boolean, nullable=True)
    is_emergency = Column(Boolean, nullable=True)
    ingest_timestamp = Column(Float, nullable=True)

    __table_args__ = (
        Index("idx_flight_telemetry_flight", "flight_id"),
    )


class ULogFile(Base):
    __tablename__ = "ulog_files"

    id = Column(String(64), primary_key=True, nullable=False)
    flight_id = Column(String(64), nullable=True)
    drone_id = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(200), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    uploaded_at = Column(BigInteger, nullable=False)
    content_type = Column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_ulog_files_flight", "flight_id"),
        Index("idx_ulog_files_drone", "drone_id"),
    )