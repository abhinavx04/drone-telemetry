from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.config import settings
from app.schemas import DroneSummary, HealthResponse, TelemetryLatestOut
from app.state import SERVICE_START_TIME, get_mqtt_snapshot, telemetry_cache
from app.mavlink_ingestor import get_ingestor_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Service health and MQTT status")
async def health() -> HealthResponse:
    mqtt = get_mqtt_snapshot()
    status = "ok" if mqtt.get("connected") else "degraded"
    return HealthResponse(status=status, mqtt=mqtt, uptime_s=int(time.time() - SERVICE_START_TIME))


@router.get("/drones", response_model=list[DroneSummary], summary="List drones with latest status")
async def read_drones() -> list[DroneSummary]:
    return await telemetry_cache.list_summaries()


@router.get(
    "/drones/{drone_id}/telemetry/latest",
    response_model=TelemetryLatestOut,
    summary="Latest sanitized telemetry for a drone",
)
async def latest_telemetry(drone_id: str) -> TelemetryLatestOut:
    snapshot = await telemetry_cache.get_latest(drone_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Unknown drone")
    if snapshot.status == "offline":
        raise HTTPException(status_code=410, detail="Drone offline")
    return snapshot


@router.get("/debug/mavlink/stats", summary="Debug stats for MAVLink ingestor")
async def mavlink_stats():
    if not settings.ingest_debug_stats:
        raise HTTPException(status_code=404, detail="Stats disabled")
    return get_ingestor_stats()


@router.websocket("/drones/{drone_id}/telemetry/stream")
async def telemetry_stream(websocket: WebSocket, drone_id: str):
    await websocket.accept()
    last_version = None
    interval = 1 / settings.ws_push_hz if settings.ws_push_hz > 0 else 0.2

    try:
        while True:
            snapshot = await telemetry_cache.get_latest(drone_id)
            if snapshot is None:
                await websocket.send_json({"type": "error", "detail": "unknown drone"})
                await websocket.close(code=4404)
                return

            if snapshot.status == "offline":
                await websocket.send_json({"type": "offline", "detail": "drone offline"})
                await websocket.close(code=4410)
                return

            if snapshot.version != last_version:
                await websocket.send_json(snapshot.model_dump())
                last_version = snapshot.version

            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("WebSocket error for %s: %s", drone_id, exc)
        await websocket.close(code=1011)