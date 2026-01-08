from __future__ import annotations

import asyncio
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.mqtt import sanitize_json_value
from app.schemas import (
    DroneSummary,
    FlightSummary,
    FlightTelemetryPage,
    FlightTelemetryPoint,
    HealthResponse,
    TelemetryImportResult,
    TelemetryLatestOut,
    ULogFileOut,
)
from app.telemetry_importer import TelemetryImporter
from app.state import SERVICE_START_TIME, get_mavlink_snapshot, get_mqtt_snapshot, telemetry_cache

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Service health and MQTT status")
async def health() -> HealthResponse:
    mqtt = get_mqtt_snapshot()
    status = "ok" if mqtt.get("connected") else "degraded"
    return HealthResponse(status=status, mqtt=mqtt, uptime_s=int(time.time() - SERVICE_START_TIME))


@router.get("/drones", response_model=list[DroneSummary], summary="List drones with latest status")
async def read_drones(db: AsyncSession = Depends(get_db)) -> list[DroneSummary]:
    registry: dict[str, dict] = {}
    try:
        result = await db.execute(
            text("SELECT drone_id, assigned_udp_port, total_flights, real_drone_id FROM drone_registry")
        )
        registry = {row["drone_id"]: dict(row) for row in result.mappings().all()}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load drone registry data: %s", exc)

    summaries = await telemetry_cache.list_summaries()
    response: list[DroneSummary] = []
    for summary in summaries:
        payload = summary.model_dump()
        reg = registry.get(summary.id)
        if reg:
            payload["udp_port"] = reg.get("assigned_udp_port")
            payload["total_flights"] = reg.get("total_flights")
            payload["real_drone_id"] = reg.get("real_drone_id")
        response.append(DroneSummary.model_validate(sanitize_json_value(payload)))
    return response


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
    sanitized = sanitize_json_value(snapshot.model_dump())
    return TelemetryLatestOut.model_validate(sanitized)


@router.get("/debug/mavlink/stats", summary="Debug stats for MAVLink ingestor")
async def mavlink_stats(drone_id: Optional[str] = None):
    if not settings.ingest_debug_stats:
        raise HTTPException(status_code=404, detail="Stats disabled")
    stats = await get_mavlink_snapshot(drone_id)
    return sanitize_json_value(stats)


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
                await websocket.send_json(sanitize_json_value(snapshot.model_dump()))
                last_version = snapshot.version

            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("WebSocket error for %s: %s", drone_id, exc)
        await websocket.close(code=1011)


@router.get(
    "/drones/{drone_id}/flights",
    response_model=list[FlightSummary],
    summary="List flights for a drone (most recent first)",
)
async def list_flights_for_drone(
    drone_id: str, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)
) -> list[FlightSummary]:
    limit = max(1, min(limit, 200))
    result = await db.execute(
        text(
            """
            SELECT flight_id, drone_id, flight_count, start_timestamp, end_timestamp, duration_seconds,
                   max_altitude_m, max_speed_mps, battery_start_pct, battery_end_pct,
                   gps_issues_count, emergency_events_count, summary_data
            FROM flights
            WHERE drone_id = :drone_id
            ORDER BY start_timestamp DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"drone_id": drone_id, "limit": limit, "offset": offset},
    )
    rows = result.mappings().all()
    return [FlightSummary.model_validate(sanitize_json_value(dict(row))) for row in rows]


@router.get("/flights/{flight_id}", response_model=FlightSummary, summary="Flight details")
async def get_flight(flight_id: str, db: AsyncSession = Depends(get_db)) -> FlightSummary:
    result = await db.execute(
        text(
            """
            SELECT flight_id, drone_id, flight_count, start_timestamp, end_timestamp, duration_seconds,
                   max_altitude_m, max_speed_mps, battery_start_pct, battery_end_pct,
                   gps_issues_count, emergency_events_count, summary_data
            FROM flights
            WHERE flight_id = :flight_id
            """
        ),
        {"flight_id": flight_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Unknown flight")
    return FlightSummary.model_validate(sanitize_json_value(dict(row)))


@router.get(
    "/flights/{flight_id}/summary",
    response_model=FlightSummary,
    summary="Flight summary (alias of flight details)",
)
async def get_flight_summary(flight_id: str, db: AsyncSession = Depends(get_db)) -> FlightSummary:
    return await get_flight(flight_id, db)


@router.get(
    "/flights/{flight_id}/telemetry",
    response_model=FlightTelemetryPage,
    summary="Flight-scoped telemetry (paginated)",
)
async def get_flight_telemetry(
    flight_id: str, limit: int = 200, offset: int = 0, db: AsyncSession = Depends(get_db)
) -> FlightTelemetryPage:
    limit = max(1, min(limit, 500))
    exists = await db.execute(text("SELECT 1 FROM flights WHERE flight_id = :flight_id"), {"flight_id": flight_id})
    if exists.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Unknown flight")

    total_res = await db.execute(
        text("SELECT COUNT(*) FROM flight_telemetry WHERE flight_id = :flight_id"), {"flight_id": flight_id}
    )
    total = int(total_res.scalar_one() or 0)
    result = await db.execute(
        text(
            """
            SELECT flight_id, timestamp, latitude, longitude, altitude_m, battery_pct, flight_mode,
                   ground_speed_mps, climb_rate_mps, heading_deg, gps_lost, is_emergency, ingest_timestamp
            FROM flight_telemetry
            WHERE flight_id = :flight_id
            ORDER BY timestamp ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"flight_id": flight_id, "limit": limit, "offset": offset},
    )
    points = [FlightTelemetryPoint.model_validate(sanitize_json_value(dict(row))) for row in result.mappings().all()]
    return FlightTelemetryPage(flight_id=flight_id, points=points, total=total, limit=limit, offset=offset)


@router.post(
    "/flights/{flight_id}/ulog",
    response_model=ULogFileOut,
    summary="Upload a ULog file for a flight",
)
async def upload_ulog(
    flight_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
) -> ULogFileOut:
    flight_row = await db.execute(
        text("SELECT drone_id FROM flights WHERE flight_id = :flight_id"), {"flight_id": flight_id}
    )
    flight = flight_row.mappings().first()
    if not flight:
        raise HTTPException(status_code=404, detail="Unknown flight")

    base_dir = Path(settings.ulog_storage_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    data = await file.read()
    file_id = str(uuid.uuid4())
    safe_name = Path(file.filename or "flight.ulg").name
    target_path = base_dir / f"{file_id}_{safe_name}"
    target_path.write_bytes(data)

    uploaded_at = int(time.time())
    await db.execute(
        text(
            """
            INSERT INTO ulog_files (id, flight_id, drone_id, file_path, original_filename, size_bytes, uploaded_at, content_type)
            VALUES (:id, :flight_id, :drone_id, :file_path, :original_filename, :size_bytes, :uploaded_at, :content_type)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": file_id,
            "flight_id": flight_id,
            "drone_id": flight["drone_id"],
            "file_path": str(target_path),
            "original_filename": safe_name,
            "size_bytes": len(data),
            "uploaded_at": uploaded_at,
            "content_type": file.content_type,
        },
    )
    await db.commit()

    logger.info("ULog uploaded flight=%s drone=%s path=%s", flight_id, flight["drone_id"], target_path)
    return ULogFileOut(
        id=file_id,
        flight_id=flight_id,
        drone_id=flight["drone_id"],
        original_filename=safe_name,
        size_bytes=len(data),
        uploaded_at=uploaded_at,
        content_type=file.content_type,
    )


@router.get(
    "/flights/{flight_id}/ulog",
    response_model=list[ULogFileOut],
    summary="List ULog files for a flight",
)
async def list_ulogs(flight_id: str, db: AsyncSession = Depends(get_db)) -> list[ULogFileOut]:
    result = await db.execute(
        text(
            """
            SELECT id, flight_id, drone_id, original_filename, size_bytes, uploaded_at, content_type
            FROM ulog_files
            WHERE flight_id = :flight_id
            ORDER BY uploaded_at DESC
            """
        ),
        {"flight_id": flight_id},
    )
    rows = result.mappings().all()
    return [ULogFileOut.model_validate(sanitize_json_value(dict(row))) for row in rows]


@router.post(
    "/drones/{drone_id}/telemetry/import",
    response_model=TelemetryImportResult,
    summary="Import historical telemetry data (CSV or JSON)",
)
async def import_historical_telemetry(
    drone_id: str,
    file: UploadFile = File(...),
    gcs_flight_count_offset: Optional[int] = None,
) -> TelemetryImportResult:
    """
    Import historical telemetry data from CSV or JSON file.

    The file should contain telemetry points with the following fields:
    - timestamp (required): Unix timestamp in seconds
    - latitude, longitude: GPS coordinates
    - altitude_m: Altitude in meters
    - battery_pct: Battery percentage
    - flight_mode: Flight mode (e.g., AUTO, MANUAL)
    - ground_speed_mps: Ground speed in m/s
    - climb_rate_mps: Climb rate in m/s
    - heading_deg: Heading in degrees
    - gps_lost: Boolean indicating GPS loss
    - is_emergency: Boolean indicating emergency mode

    The system will:
    1. Detect flight boundaries automatically
    2. Create flight records
    3. Import telemetry points
    4. Detect problems and anomalies
    5. Calculate statistics

    Args:
        drone_id: Drone identifier (e.g., "udp:14540")
        file: Telemetry file (CSV or JSON)
        gcs_flight_count_offset: Optional offset for flight count numbering (if GCS has its own numbering)

    Returns:
        ImportResult with details of imported flights and detected problems
    """
    try:
        # Read file content
        content = await file.read()

        # Import telemetry
        importer = TelemetryImporter()
        result = await importer.import_from_file(
            drone_id=drone_id,
            file_content=content,
            filename=file.filename or "telemetry.csv",
            gcs_flight_count_offset=gcs_flight_count_offset,
        )

        logger.info(
            "Telemetry import completed for %s: %d flights, %d points, %d problems",
            drone_id,
            result.flights_created,
            result.telemetry_points_imported,
            result.problems_detected,
        )

        return TelemetryImportResult(
            flights_created=result.flights_created,
            telemetry_points_imported=result.telemetry_points_imported,
            problems_detected=result.problems_detected,
            flight_ids=result.flight_ids,
            warnings=result.warnings,
            errors=result.errors,
        )

    except ValueError as exc:
        logger.error("Invalid telemetry file for %s: %s", drone_id, exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to import telemetry for %s: %s", drone_id, exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Import failed: {exc}"
        ) from exc