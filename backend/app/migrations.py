from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def _create_tables(conn) -> None:
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS drone_registry (
                drone_id VARCHAR(50) PRIMARY KEY,
                assigned_udp_port INTEGER UNIQUE NOT NULL,
                total_flights INTEGER NOT NULL DEFAULT 0,
                last_seen_timestamp BIGINT,
                serial_number VARCHAR(50),
                real_drone_id VARCHAR(100),
                created_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW())),
                updated_at BIGINT NOT NULL DEFAULT (EXTRACT(EPOCH FROM NOW()))
            )
            """
        )
    )

    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS flights (
                flight_id VARCHAR(64) PRIMARY KEY,
                drone_id VARCHAR(50) NOT NULL,
                flight_count INTEGER NOT NULL,
                start_timestamp BIGINT NOT NULL,
                end_timestamp BIGINT,
                duration_seconds INTEGER,
                max_altitude_m DOUBLE PRECISION,
                max_speed_mps DOUBLE PRECISION,
                battery_start_pct DOUBLE PRECISION,
                battery_end_pct DOUBLE PRECISION,
                gps_issues_count INTEGER NOT NULL DEFAULT 0,
                emergency_events_count INTEGER NOT NULL DEFAULT 0,
                summary_data JSONB,
                CONSTRAINT uq_flights_drone_flight_count UNIQUE (drone_id, flight_count)
            )
            """
        )
    )
    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_flights_drone ON flights(drone_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_flights_start_ts ON flights(start_timestamp)"))

    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS flight_telemetry (
                flight_id VARCHAR(64) NOT NULL,
                timestamp BIGINT NOT NULL,
                drone_id VARCHAR(50) NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                altitude_m DOUBLE PRECISION,
                battery_pct DOUBLE PRECISION,
                flight_mode VARCHAR(50),
                ground_speed_mps DOUBLE PRECISION,
                climb_rate_mps DOUBLE PRECISION,
                heading_deg DOUBLE PRECISION,
                gps_lost BOOLEAN,
                is_emergency BOOLEAN,
                ingest_timestamp DOUBLE PRECISION,
                PRIMARY KEY (flight_id, timestamp)
            )
            """
        )
    )
    await conn.execute(
        text("CREATE INDEX IF NOT EXISTS idx_flight_telemetry_flight ON flight_telemetry(flight_id)")
    )

    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS ulog_files (
                id VARCHAR(64) PRIMARY KEY,
                flight_id VARCHAR(64),
                drone_id VARCHAR(50) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                original_filename VARCHAR(200) NOT NULL,
                size_bytes BIGINT NOT NULL,
                uploaded_at BIGINT NOT NULL,
                content_type VARCHAR(100)
            )
            """
        )
    )
    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ulog_files_flight ON ulog_files(flight_id)"))
    await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ulog_files_drone ON ulog_files(drone_id)"))


async def _ensure_timescale(conn) -> None:
    try:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
        await conn.execute(
            text(
                "SELECT create_hypertable('flight_telemetry', 'timestamp', if_not_exists => TRUE, chunk_time_interval => 86400)"
            )
        )
        logger.info("TimescaleDB hypertable ensured for flight_telemetry")
    except Exception as exc:  # noqa: BLE001
        logger.info("TimescaleDB not available or hypertable creation skipped: %s", exc)


async def run_migrations(engine: AsyncEngine) -> None:
    """
    Idempotent, startup-run migrations. This MUST NOT touch the existing telemetry table.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SET lock_timeout TO '5s'"))
            await _create_tables(conn)
            await _ensure_timescale(conn)
        logger.info("Migrations completed")
    except Exception as exc:  # noqa: BLE001
        logger.error("Migration failure (continuing without blocking startup): %s", exc, exc_info=True)

