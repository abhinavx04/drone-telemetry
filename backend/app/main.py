import asyncio
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api import router as api_router
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.db import get_db, Base, engine
from app.schemas import TelemetryOut, TelemetryIn
from app.crud import get_recent_telemetry, create_telemetry
from app.utils import setup_logging
from app.mqtt import mqtt_listener

app = FastAPI(title="Drone Telemetry API", version="1.0.0")

# CORS Middleware to allow the React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include versioned API router
app.include_router(api_router, prefix="/api/v1")

setup_logging(settings.log_level)

@app.on_event("startup")
async def startup_event():
    # Create tables if not exists
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Start MQTT listener in background
    app.state.mqtt_task = asyncio.create_task(mqtt_listener())
    logging.getLogger("main").info("Service started")

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "mqtt_task"):
        app.state.mqtt_task.cancel()
        try:
            await app.state.mqtt_task
        except asyncio.CancelledError:
            pass
    await engine.dispose()
    logging.getLogger("main").info("Service shutdown")

@app.get("/health", summary="Health check")
async def health_check():
    return {"status": "ok"}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Drone Telemetry API"}

@app.post("/telemetry/", response_model=TelemetryOut, status_code=201)
async def post_telemetry(telemetry: TelemetryIn, db=Depends(get_db)):
    try:
        obj = await create_telemetry(db, telemetry)
        return obj
    except SQLAlchemyError as e:
        logging.error(f"DB error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/telemetry/{drone_id}", response_model=list[TelemetryOut])
async def list_telemetry(drone_id: str, limit: int = 10, db=Depends(get_db)):
    try:
        objs = await get_recent_telemetry(db, drone_id, limit)
        return objs
    except SQLAlchemyError as e:
        logging.error(f"DB error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )