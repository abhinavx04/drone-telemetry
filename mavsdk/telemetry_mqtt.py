import asyncio
import argparse
import json
from datetime import datetime, timezone
from mavsdk import System
import paho.mqtt.client as mqtt
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class DroneState:
    def __init__(self):
        self.battery_percent = None     # No assumption of default
        self.flight_mode = None
        self.is_armed = None
        self.gps_fix = None
        self.system_status = None

async def run(args):
    drone = System()
    await drone.connect(system_address=f"udp://:{args.port}")
    logging.info(f"Connecting to drone on UDP port {args.port}...")

    # Wait for connection
    async for state in drone.core.connection_state():
        if state.is_connected:
            logging.info(f"Drone discovered: {args.drone_id}")
            break

    client = mqtt.Client()
    try:
        client.connect(args.mqtt_host, args.mqtt_port, 60)
        client.loop_start()
        logging.info(f"Connected to MQTT broker at {args.mqtt_host}:{args.mqtt_port}")
    except Exception as e:
        logging.error(f"MQTT connection failed: {e}")
        return

    drone_state = DroneState()

    # Start all telemetry streams with defensive wrappers
    tasks = [
        asyncio.create_task(wrap_monitor(monitor_battery, drone, drone_state)),
        asyncio.create_task(wrap_monitor(monitor_flight_mode, drone, drone_state)),
        asyncio.create_task(wrap_monitor(monitor_armed, drone, drone_state)),
        asyncio.create_task(wrap_monitor(monitor_gps, drone, drone_state)),
        asyncio.create_task(wrap_monitor(monitor_system_status, drone, drone_state)),
        asyncio.create_task(monitor_position(drone, drone_state, client, args.drone_id)),
    ]

    # Wait for all tasks
    await asyncio.gather(*tasks)

async def wrap_monitor(func, *args):
    """Wrapper to log exceptions in background monitors."""
    try:
        await func(*args)
    except Exception as e:
        logging.error(f"Error in telemetry monitor {func.__name__}: {e}", exc_info=True)

async def monitor_battery(drone, drone_state):
    async for battery in drone.telemetry.battery():
        if battery is not None and battery.remaining_percent is not None:
            drone_state.battery_percent = battery.remaining_percent * 100
        else:
            logging.warning("Missing battery data")

async def monitor_flight_mode(drone, drone_state):
    async for flight_mode in drone.telemetry.flight_mode():
        mode = str(flight_mode) if flight_mode is not None else None
        # Map MAVSDK modes to backend schema
        if mode == "FlightMode.RETURN_TO_LAUNCH":
            drone_state.flight_mode = "Return to Launch"
        elif mode == "FlightMode.POSITION":
            drone_state.flight_mode = "Position Hold"
        elif mode:
            drone_state.flight_mode = mode.replace("FlightMode.", "").replace("_", " ").title()
        else:
            logging.warning("Missing flight mode data")

async def monitor_armed(drone, drone_state):
    async for armed in drone.telemetry.armed():
        # Will be None briefly; log and skip
        if armed is None:
            logging.warning("Missing armed state data")
            continue
        drone_state.is_armed = armed

async def monitor_gps(drone, drone_state):
    async for gps_info in drone.telemetry.gps_info():
        # Defensive: some MAVSDK versions may have gps_info.fix_type as enum/non-enum
        try:
            fix_val = int(getattr(gps_info.fix_type, "value", gps_info.fix_type))
        except (AttributeError, TypeError):
            fix_val = 0
        drone_state.gps_fix = fix_val >= 3  # 3 or above = 3D Fix

async def monitor_system_status(drone, drone_state):
    # Might be rc_status/system_status or similar per MAVSDK—you may need to tweak
    async for status in drone.telemetry.health_all_ok():
        # Using 'health_all_ok' as a placeholder; replace with correct stream!
        # Set to "OK" for bool True; else "ERROR"
        if status is not None:
            drone_state.system_status = "OK" if status else "ERROR"
        else:
            logging.warning("Missing system status/health data")

async def monitor_position(drone, drone_state, client, drone_id):
    async for position in drone.telemetry.position():
        # Defensive checks
        if position is None or position.latitude_deg is None or position.longitude_deg is None or position.absolute_altitude_m is None:
            logging.warning("Incomplete position data; skipping publish")
            continue

        now_iso = datetime.now(timezone.utc).isoformat()

        data = {
            "drone_id": drone_id,
            "latitude": position.latitude_deg,
            "longitude": position.longitude_deg,
            "absolute_altitude_m": position.absolute_altitude_m,
            "timestamp": now_iso,
            "battery_percentage": drone_state.battery_percent if drone_state.battery_percent is not None else -1,
            "flight_mode": drone_state.flight_mode if drone_state.flight_mode else "Unknown",
            "is_online": True
        }

        # Log telemetry data periodically
        logging.info(f"Publishing telemetry: {data}")

        topic = f"drone/{drone_id}/telemetry"
        try:
            client.publish(topic, json.dumps(data))
        except Exception as e:
            logging.error(f"MQTT publish failed: {e}")

        await asyncio.sleep(0.5)  # Reduce frequency to avoid flooding

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--drone-id", required=True)
    parser.add_argument("--mqtt-host", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        logging.info("Telemetry publisher stopped by user")
