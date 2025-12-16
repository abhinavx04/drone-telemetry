from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Optional

from asyncio_mqtt import Client, MqttError
from paho.mqtt import client as paho_mqtt
from pydantic import ValidationError

from app.config import settings
from app.crud import create_telemetry
from app.db import AsyncSessionLocal
from app.schemas import NormalizedTelemetry, Position, TelemetryDerived, TelemetryFlags, TelemetryIn
from app.state import mqtt_state, telemetry_cache

logger = logging.getLogger("mqtt")

_worker_semaphore = asyncio.Semaphore(settings.ingest_max_concurrency)
_pending_tasks: set[asyncio.Task] = set()
_MAX_BACKLOG = settings.ingest_backlog_max
_publish_lock = threading.Lock()
_publish_client: Optional[paho_mqtt.Client] = None

BACKEND_INGEST_SOURCE = "backend_ingestor"

_FLIGHT_MODE_MAP = {
    "MANUAL": "MANUAL",
    "ALTCTL": "ALT_HOLD",
    "ALT_HOLD": "ALT_HOLD",
    "POSCTL": "POS_HOLD",
    "POS_HOLD": "POS_HOLD",
    "AUTO.MISSION": "MISSION",
    "MISSION": "MISSION",
    "AUTO.RTL": "RTL",
    "RTL": "RTL",
    "LAND": "LAND",
    "OFFBOARD": "OFFBOARD",
}


def _normalize_flight_mode(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    normalized = _FLIGHT_MODE_MAP.get(raw.strip().upper())
    return normalized or "UNKNOWN"


def _normalize_payload(raw: TelemetryIn) -> NormalizedTelemetry:
    now = time.time()
    source_ts = int(raw.timestamp) if raw.timestamp is not None else int(now)

    gps_lost = False
    position = None
    if raw.latitude is not None and raw.longitude is not None:
        if -90 <= raw.latitude <= 90 and -180 <= raw.longitude <= 180:
            position = Position(lat=raw.latitude, lon=raw.longitude, alt_m=raw.absolute_altitude_m)
        else:
            gps_lost = True
    else:
        gps_lost = True

    battery_pct = None
    if raw.battery_percentage is not None:
        battery_pct = max(0.0, min(100.0, float(raw.battery_percentage)))

    is_emergency = bool(raw.is_emergency) or (battery_pct is not None and battery_pct <= settings.emergency_battery_pct)
    flags = TelemetryFlags(gps_lost=gps_lost, rc_lost=raw.rc_lost, is_emergency=is_emergency)
    derived = TelemetryDerived(
        ground_speed_mps=raw.ground_speed_mps,
        climb_rate_mps=raw.climb_rate_mps,
        heading_deg=raw.heading_deg,
    )

    return NormalizedTelemetry(
        drone_id=raw.drone_id.strip(),
        source_timestamp=source_ts,
        ingest_timestamp=now,
        position=position,
        battery_pct=battery_pct,
        flight_mode=_normalize_flight_mode(raw.flight_mode),
        flags=flags,
        derived=derived,
    )

def normalized_to_payload(normalized: NormalizedTelemetry, include_ingest_source: bool = False) -> dict:
    payload = {
        "drone_id": normalized.drone_id,
        "timestamp": normalized.source_timestamp,
        "latitude": normalized.position.lat if normalized.position else None,
        "longitude": normalized.position.lon if normalized.position else None,
        "absolute_altitude_m": normalized.position.alt_m if normalized.position else None,
        "battery_percentage": normalized.battery_pct,
        "flight_mode": normalized.flight_mode,
        "ground_speed_mps": normalized.derived.ground_speed_mps,
        "climb_rate_mps": normalized.derived.climb_rate_mps,
        "heading_deg": normalized.derived.heading_deg,
        "rc_lost": normalized.flags.rc_lost,
        "gps_fix": None if normalized.flags.gps_lost is None else not normalized.flags.gps_lost,
        "is_emergency": normalized.flags.is_emergency,
    }
    if include_ingest_source:
        payload["ingest_source"] = BACKEND_INGEST_SOURCE
    # Drop keys with value None to keep payload compact
    return {k: v for k, v in payload.items() if v is not None}


def _ensure_publish_client() -> Optional[paho_mqtt.Client]:
    global _publish_client
    if _publish_client and _publish_client.is_connected():
        return _publish_client
    try:
        client = paho_mqtt.Client(client_id="backend-ingestor-pub")
        client.connect(settings.mqtt_host, settings.mqtt_port, 60)
        client.loop_start()
        _publish_client = client
        return client
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to init MQTT publish client: %s", exc)
        return None


def publish_normalized(normalized: NormalizedTelemetry, payload: Optional[dict] = None) -> None:
    """
    Synchronous publish for the ingestion thread. Avoids feedback loops by tagging ingest_source.
    """
    if payload is None:
        payload = normalized_to_payload(normalized, include_ingest_source=True)
    topic = f"drone/{normalized.drone_id}/telemetry"
    with _publish_lock:
        client = _ensure_publish_client()
        if client is None:
            return
        try:
            client.publish(topic, json.dumps(payload), qos=0, retain=False)
            mqtt_state["last_message_ts"] = time.time()
        except Exception as exc:  # noqa: BLE001
            logger.error("MQTT publish failed for %s: %s", topic, exc)
            mqtt_state["last_error"] = str(exc)

async def _persist_if_possible(normalized: NormalizedTelemetry) -> None:
    if normalized.position is None:
        logger.debug("Skipping DB persist for %s because position is missing/invalid", normalized.drone_id)
        return

    db_payload = TelemetryIn(
        drone_id=normalized.drone_id,
        latitude=normalized.position.lat,
        longitude=normalized.position.lon,
        absolute_altitude_m=normalized.position.alt_m,
        timestamp=normalized.source_timestamp,
        battery_percentage=normalized.battery_pct,
        flight_mode=normalized.flight_mode,
        is_online=True,
    )

    try:
        async with AsyncSessionLocal() as db:
            await create_telemetry(db, db_payload)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to persist telemetry for %s: %s", normalized.drone_id, exc)


async def persist_normalized(normalized: NormalizedTelemetry) -> None:
    """Shared persistence helper for other ingestion paths."""
    await _persist_if_possible(normalized)


async def handle_mqtt_message(payload: bytes) -> None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in MQTT message: %s | Payload: %s", exc, payload)
        return

    if isinstance(data, dict) and data.get("ingest_source") == BACKEND_INGEST_SOURCE:
        logger.debug("Skipping backend-ingestor loopback for %s", data.get("drone_id"))
        return

    try:
        raw = TelemetryIn.model_validate(data)
    except ValidationError as exc:
        logger.error("Validation error in MQTT message: %s | Payload: %s", exc, payload)
        return

    if not raw.drone_id or not raw.drone_id.strip():
        logger.error("Received telemetry without drone_id. Dropping payload: %s", payload)
        return

    normalized = _normalize_payload(raw)
    await telemetry_cache.update(normalized)
    await _persist_if_possible(normalized)
    logger.debug("Processed telemetry for %s", normalized.drone_id)


async def _worker(payload: bytes) -> None:
    async with _worker_semaphore:
        await handle_mqtt_message(payload)


async def mqtt_listener():
    while True:
        try:
            logger.info("Connecting to MQTT broker at %s:%s", settings.mqtt_host, settings.mqtt_port)
            async with Client(settings.mqtt_host, settings.mqtt_port) as client:
                mqtt_state.update({"connected": True, "last_error": None})
                async with client.unfiltered_messages() as messages:
                    await client.subscribe(settings.mqtt_topic)
                    logger.info("MQTT subscribed to %s", settings.mqtt_topic)
                    async for message in messages:
                        mqtt_state["last_message_ts"] = time.time()
                        if len(_pending_tasks) >= _MAX_BACKLOG:
                            logger.warning(
                                "Dropping telemetry message due to backlog size=%s (limit=%s)",
                                len(_pending_tasks),
                                _MAX_BACKLOG,
                            )
                            continue
                        try:
                            task = asyncio.create_task(_worker(message.payload))
                            _pending_tasks.add(task)
                            task.add_done_callback(_pending_tasks.discard)
                        except Exception as exc:  # noqa: BLE001
                            logger.error("Failed to schedule MQTT handling: %s", exc)
        except MqttError as exc:
            mqtt_state.update({"connected": False, "last_error": str(exc)})
            logger.error(
                "MQTT connection error: %s. Retrying in %s seconds...", exc, settings.mqtt_reconnect_delay
            )
            await asyncio.sleep(settings.mqtt_reconnect_delay)
        except Exception as exc:  # noqa: BLE001
            mqtt_state.update({"connected": False, "last_error": str(exc)})
            logger.error("Unknown MQTT error: %s. Retrying in %s seconds...", exc, settings.mqtt_reconnect_delay)
            await asyncio.sleep(settings.mqtt_reconnect_delay)