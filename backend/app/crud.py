from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from app.models import Telemetry
from app.schemas import TelemetryIn

async def create_telemetry(db: AsyncSession, telemetry: TelemetryIn):
    db_obj = Telemetry(**telemetry.dict())
    db.add(db_obj)
    try:
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    except SQLAlchemyError as e:
        await db.rollback()
        raise e

async def get_recent_telemetry(db: AsyncSession, drone_id: str, limit: int = 10):
    stmt = select(Telemetry).where(Telemetry.drone_id == drone_id).order_by(Telemetry.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()