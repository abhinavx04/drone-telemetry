import asyncio
import argparse
import json
from datetime import datetime, timezone
from mavsdk import System
import paho.mqtt.client as mqtt

class DroneState:
    def __init__(self):
        self.flight_count = 0
        self.is_flying = False
        self.trajectory = []
        self.last_position = None
        self.emergency_reasons = set()
        self.battery_percent = 100.0
        self.flight_mode = "manual"
        self.is_armed = False
        self.gps_fix = False
        self.system_status = "UNKNOWN"

    def update_emergency_status(self):
        self.emergency_reasons.clear()
        
        # Low battery alert (below 20%)
        if self.battery_percent < 20:
            self.emergency_reasons.add("low_battery")
            
        # GPS loss
        if not self.gps_fix:
            self.emergency_reasons.add("gps_loss")
            
        # System failure
        if self.system_status in ["ERROR", "CRITICAL"]:
            self.emergency_reasons.add("system_failure")
            
        # Loss of control
        if not self.is_armed:
            self.emergency_reasons.add("loss_of_control")
            
        return len(self.emergency_reasons) > 0, list(self.emergency_reasons)

async def run(args):
    drone = System()
    await drone.connect(system_address=f"udp://:{args.port}")
    print(f"Connecting to drone on UDP port {args.port}...")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"Drone discovered: {args.drone_id}")
            break

    client = mqtt.Client()
    client.connect(args.mqtt_host, args.mqtt_port, 60)
    client.loop_start()

    drone_state = DroneState()

    # Start all telemetry streams
    battery_task = asyncio.create_task(monitor_battery(drone, drone_state))
    flight_mode_task = asyncio.create_task(monitor_flight_mode(drone, drone_state))
    armed_task = asyncio.create_task(monitor_armed(drone, drone_state))
    gps_task = asyncio.create_task(monitor_gps(drone, drone_state))
    system_status_task = asyncio.create_task(monitor_system_status(drone, drone_state))
    position_task = asyncio.create_task(monitor_position(drone, drone_state, client, args.drone_id))

    # Wait for all tasks
    await asyncio.gather(
        battery_task,
        flight_mode_task,
        armed_task,
        gps_task,
        system_status_task,
        position_task
    )

async def monitor_battery(drone, drone_state):
    async for battery in drone.telemetry.battery():
        drone_state.battery_percent = battery.remaining_percent * 100

async def monitor_flight_mode(drone, drone_state):
    async for flight_mode in drone.telemetry.flight_mode():
        mode = str(flight_mode)
        if mode == "RETURN_TO_LAUNCH":
            drone_state.flight_mode = "rth"
        elif mode == "POSITION":
            drone_state.flight_mode = "atti"
        else:
            drone_state.flight_mode = "manual"

async def monitor_armed(drone, drone_state):
    async for armed in drone.telemetry.armed():gi
        if armed and not drone_state.is_flying:
            drone_state.is_flying = True
        elif not armed and drone_state.is_flying:
            drone_state.is_flying = False
            drone_state.flight_count += 1
        drone_state.is_armed = armed

async def monitor_gps(drone, drone_state):
    async for gps_info in drone.telemetry.gps_info():
        drone_state.gps_fix = gps_info.fix_type >= 3  # 3 or higher indicates 3D fix

async def monitor_system_status(drone, drone_state):
    async for status in drone.telemetry.status():
        drone_state.system_status = status.system_status

async def monitor_position(drone, drone_state, client, drone_id):
    async for position in drone.telemetry.position():
        # Update trajectory
        if drone_state.last_position is None or (
            abs(position.latitude_deg - drone_state.last_position.latitude_deg) > 0.0001 or
            abs(position.longitude_deg - drone_state.last_position.longitude_deg) > 0.0001
        ):
            drone_state.trajectory.append({
                "latitude": position.latitude_deg,
                "longitude": position.longitude_deg,
                "timestamp": int(datetime.now(timezone.utc).timestamp())
            })
            # Keep only last 1000 points to prevent memory issues
            if len(drone_state.trajectory) > 1000:
                drone_state.trajectory = drone_state.trajectory[-1000:]
            drone_state.last_position = position

        # Update emergency status
        is_emergency, emergency_reasons = drone_state.update_emergency_status()

        data = {
            "drone_id": drone_id,
            "latitude": position.latitude_deg,
            "longitude": position.longitude_deg,
            "absolute_altitude_m": position.absolute_altitude_m,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "battery_percentage": drone_state.battery_percent,
            "flight_mode": drone_state.flight_mode,
            "is_online": True,
            "flight_count": drone_state.flight_count,
            "emergency_status": is_emergency,
            "emergency_reasons": emergency_reasons,
            "trajectory": drone_state.trajectory
        }
        
        topic = f"drone/{drone_id}/telemetry"
        client.publish(topic, json.dumps(data))
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--drone-id", required=True)
    parser.add_argument("--mqtt-host", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    args = parser.parse_args()
    asyncio.run(run(args))