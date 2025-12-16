import asyncio
import logging
import time

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import router as api_router
from app.config import settings
from app.crud import create_telemetry, get_recent_telemetry
from app.db import Base, engine, get_db
from app.mqtt import mqtt_listener
from app.mavlink_ingestor import start_ingestor, stop_ingestor
from app.schemas import TelemetryIn, TelemetryOut
from app.state import SERVICE_START_TIME, get_mqtt_snapshot
from app.utils import setup_logging

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
    # Start MAVLink UDP ingestor in a daemon thread; uses the server loop for callbacks.
    loop = asyncio.get_running_loop()
    start_ingestor(loop)
    logging.getLogger("main").info("Service started")

@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "mqtt_task"):
        app.state.mqtt_task.cancel()
        try:
            await app.state.mqtt_task
        except asyncio.CancelledError:
            pass
    stop_ingestor()
    await engine.dispose()
    logging.getLogger("main").info("Service shutdown")

@app.get("/health", summary="Health check")
async def health_check():
    mqtt = get_mqtt_snapshot()
    status = "ok" if mqtt.get("connected") else "degraded"
    return {"status": status, "mqtt": mqtt, "uptime_s": int(time.time() - SERVICE_START_TIME)}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Drone Telemetry API"}

@app.post("/telemetry/", response_model=TelemetryOut, status_code=201)
async def post_telemetry(telemetry: TelemetryIn, db=Depends(get_db)):
    try:
        obj = await create_telemetry(db, telemetry)
        return obj
    except ValueError as exc:
        logging.error("Bad telemetry payload: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
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