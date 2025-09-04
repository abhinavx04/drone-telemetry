from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

from app import crud
from app.db import get_db
from app.schemas import TelemetryOut

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/drones", response_model=List[TelemetryOut])
async def read_all_drones_status(db: AsyncSession = Depends(get_db)):
    """
    Retrieve the latest status for all unique drones.
    """
    try:
        drones = await crud.get_all_drones_latest_telemetry(db)
        return drones if drones else []
    except Exception as e:
        logger.error(f"API Error fetching all drones status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")