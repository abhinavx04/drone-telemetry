import asyncio
import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router as api_router
from app.config import settings
from app.db import Base, engine
from app.mqtt import mqtt_listener, publish_fleet_summary
from app.mavlink_ingestor import start_ingestor, stop_ingestor
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

    # Optional MQTT listener (ingestion disabled by default)
    if settings.ingest_enable_mqtt_listener:
        app.state.mqtt_task = asyncio.create_task(mqtt_listener())

    # Fleet summary publisher
    app.state.summary_stop = asyncio.Event()
    app.state.summary_task = asyncio.create_task(publish_fleet_summary(app.state.summary_stop))

    await start_ingestor()
    logging.getLogger("main").info("Service started")


@app.on_event("shutdown")
async def shutdown_event():
    if hasattr(app.state, "mqtt_task"):
        app.state.mqtt_task.cancel()
        try:
            await app.state.mqtt_task
        except asyncio.CancelledError:
            pass
    if hasattr(app.state, "summary_stop"):
        app.state.summary_stop.set()
    if hasattr(app.state, "summary_task"):
        try:
            await app.state.summary_task
        except asyncio.CancelledError:
            pass

    await stop_ingestor()
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


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logging.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})