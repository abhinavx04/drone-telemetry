import asyncio
import json
import logging
from asyncio_mqtt import Client, MqttError
from app.config import settings
from app.schemas import TelemetryIn
from app.crud import create_telemetry
from app.db import AsyncSessionLocal

logger = logging.getLogger("mqtt")

async def handle_mqtt_message(payload: bytes):
    try:
        data = json.loads(payload)
        logger.debug(f"Received MQTT payload: {data}")
        
        # Log timestamp type before conversion
        if 'timestamp' in data:
            logger.debug(f"Timestamp type before conversion: {type(data['timestamp'])}")
        
        telemetry = TelemetryIn(**data)
        
        # Log timestamp type after conversion
        logger.debug(f"Timestamp type after conversion: {type(telemetry.timestamp)}")
        logger.debug(f"Timestamp value: {telemetry.timestamp}")
        
        async with AsyncSessionLocal() as db:
            await create_telemetry(db, telemetry)
        logger.info(f"Successfully saved telemetry for drone {telemetry.drone_id}")
    except ValueError as e:
        logger.error(f"Validation error in MQTT message: {e} | Payload: {payload}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in MQTT message: {e} | Payload: {payload}")
    except Exception as e:
        logger.error(f"Failed to handle MQTT message: {e} | Payload: {payload}")

async def mqtt_listener():
    while True:
        try:
            async with Client(settings.mqtt_host, settings.mqtt_port) as client:
                async with client.unfiltered_messages() as messages:
                    await client.subscribe(settings.mqtt_topic)
                    logger.info(f"MQTT subscribed to {settings.mqtt_topic}")
                    async for message in messages:
                        asyncio.create_task(handle_mqtt_message(message.payload))
        except MqttError as e:
            logger.error(f"MQTT connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unknown MQTT error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)