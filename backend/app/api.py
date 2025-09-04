from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import crud, schemas
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/drones", response_model=list[schemas.Drone])
def read_drones(db: Session = Depends(get_db)):
    try:
        logger.info("Fetching drones from the database.")
        drones = crud.get_drones(db)
        logger.info(f"Found {len(drones)} drones.")
        return drones
    except Exception as e:
        logger.error(f"Error fetching drones: {e}", exc_info=True)
        # This is the corrected line
        raise HTTPException(status_code=500, detail="Internal server error")