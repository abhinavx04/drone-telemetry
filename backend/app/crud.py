from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from typing import List
import logging
from app.models import Telemetry
from app.schemas import TelemetryIn

logger = logging.getLogger(__name__)

async def create_telemetry(db: AsyncSession, telemetry: TelemetryIn) -> Telemetry:
    """
    Create a new telemetry record.
    
    Args:
        db: Database session
        telemetry: Telemetry data with validated timestamp (integer Unix timestamp)
        
    Returns:
        Created Telemetry record
        
    Raises:
        SQLAlchemyError: If database operation fails
        ValueError: If timestamp is not an integer
    """
    try:
        # Ensure timestamp is integer (should be handled by schema validator, but double-check)
        if not isinstance(telemetry.timestamp, int):
            logger.error(f"Invalid timestamp type: {type(telemetry.timestamp)}")
            raise ValueError("Timestamp must be an integer Unix timestamp")
            
        # Log the data being inserted
        logger.debug(f"Creating telemetry record: drone_id={telemetry.drone_id}, timestamp={telemetry.timestamp}")
        
        db_obj = Telemetry(**telemetry.dict())
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
    """
    Get recent telemetry records for a drone.
    
    Args:
        db: Database session
        drone_id: ID of the drone
        limit: Maximum number of records to return
        
    Returns:
        List of Telemetry records
    """
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