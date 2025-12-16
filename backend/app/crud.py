from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select, text
from typing import List
import logging
from app.models import Telemetry
from app.schemas import TelemetryIn

logger = logging.getLogger(__name__)

async def create_telemetry(db: AsyncSession, telemetry: TelemetryIn) -> Telemetry:
    try:
        if telemetry.latitude is None or telemetry.longitude is None:
            raise ValueError("Latitude and longitude are required for persistence")
        if telemetry.timestamp is None or not isinstance(telemetry.timestamp, int):
            raise ValueError("Timestamp must be an integer Unix timestamp")
        
        # Only include fields that exist in the Telemetry model
        # This prevents SQLAlchemy errors from unknown keyword arguments
        payload = {
            "drone_id": telemetry.drone_id,
            "timestamp": telemetry.timestamp,
            "latitude": telemetry.latitude,
            "longitude": telemetry.longitude,
            "absolute_altitude_m": telemetry.absolute_altitude_m,
            "battery_percentage": telemetry.battery_percentage,
            "flight_mode": telemetry.flight_mode,
            "is_online": telemetry.is_online if telemetry.is_online is not None else True,
            "rc_lost": telemetry.rc_lost,
            "gps_fix": telemetry.gps_fix,
            "is_emergency": telemetry.is_emergency,
        }
        logger.debug(
            "Creating telemetry record: drone_id=%s, timestamp=%s", telemetry.drone_id, telemetry.timestamp
        )
        
        db_obj = Telemetry(**payload)
        db.add(db_obj)
        
        try:
            await db.commit()
            await db.refresh(db_obj)
            logger.info(f"Successfully created telemetry record for drone {telemetry.drone_id}")
            return db_obj
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Database error while creating telemetry: {e}")
            raise e
    except Exception as e:
        logger.error(f"Unexpected error in create_telemetry: {e}")
        raise

async def get_recent_telemetry(db: AsyncSession, drone_id: str, limit: int = 10) -> List[Telemetry]:
    """... (existing function remains unchanged) ..."""
    try:
        logger.debug(f"Fetching recent telemetry for drone {drone_id}, limit={limit}")
        stmt = select(Telemetry).where(Telemetry.drone_id == drone_id).order_by(Telemetry.timestamp.desc()).limit(limit)
        result = await db.execute(stmt)
        records = result.scalars().all()
        logger.debug(f"Found {len(records)} telemetry records")
        return records
    except Exception as e:
        logger.error(f"Error fetching telemetry records: {e}")
        raise

async def get_all_drones_latest_telemetry(db: AsyncSession) -> List[Telemetry]:
    """
    Gets the most recent telemetry record for every unique drone.
    This uses a PostgreSQL-specific feature 'DISTINCT ON' for efficiency.
    """
    try:
        logger.debug("Fetching latest telemetry for all drones")
        query = text("""
            SELECT DISTINCT ON (drone_id) *
            FROM telemetry
            ORDER BY drone_id, timestamp DESC;
        """)
        result = await db.execute(query)
        records = result.mappings().all() # Use .mappings() to get dict-like rows
        logger.debug(f"Found latest telemetry for {len(records)} unique drones")
        return records
    except Exception as e:
        logger.error(f"Error fetching latest telemetry for all drones: {e}")
        raise