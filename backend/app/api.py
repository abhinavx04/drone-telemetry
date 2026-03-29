import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/drones", response_model=list[schemas.Drone])
async def read_drones(db: AsyncSession = Depends(get_db)):
    try:
        logger.info("Fetching drones (latest telemetry per drone).")
        drones = await crud.get_drones(db)
        logger.info("Found %s drones.", len(drones))
        return drones
    except SQLAlchemyError as e:
        logger.error("Database error fetching drones: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
    except Exception as e:
        logger.error("Error fetching drones: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e
