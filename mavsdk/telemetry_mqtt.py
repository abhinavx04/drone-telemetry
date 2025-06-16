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

    def update_emergency_status(self, battery_percent, gps_fix, system_status, control_status, obstacle_detected):
        self.emergency_reasons.clear()
        
        # Low battery alert (below 20%)
        if battery_percent < 20:
            self.emergency_reasons.add("low_battery")
            
        # GPS loss
        if not gps_fix:
            self.emergency_reasons.add("gps_loss")
            
        # System failure
        if system_status in ["ERROR", "CRITICAL"]:
            self.emergency_reasons.add("system_failure")
            
        # Loss of control
        if not control_status:
            self.emergency_reasons.add("loss_of_control")
            
        # Obstacle detection
        if obstacle_detected:
            self.emergency_reasons.add("obstacle_detected")
            
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

    # Subscribe to flight mode changes
    async for flight_mode in drone.telemetry.flight_mode():
        current_mode = str(flight_mode)
        if current_mode == "RETURN_TO_LAUNCH":
            current_mode = "rth"
        elif current_mode == "POSITION":
            current_mode = "atti"
        else:
            current_mode = "manual"

        # Get battery info
        battery = await drone.telemetry.battery()
        battery_percent = battery.remaining_percent * 100
        
        # Get GPS status
        gps_info = await drone.telemetry.gps_info()
        gps_fix = gps_info.fix_type >= 3  # 3 or higher indicates 3D fix
        
        # Get system status
        status = await drone.telemetry.status()
        system_status = status.system_status
        
        # Get control status (armed state)
        armed = await drone.telemetry.armed()
        
        # Get obstacle detection status (if available)
        try:
            obstacle_info = await drone.telemetry.obstacle_distance()
            obstacle_detected = any(distance < 2.0 for distance in obstacle_info.distances)  # 2 meters threshold
        except:
            obstacle_detected = False
        
        # Update emergency status
        is_emergency, emergency_reasons = drone_state.update_emergency_status(
            battery_percent,
            gps_fix,
            system_status,
            armed,
            obstacle_detected
        )
        
        # Update flight count
        if armed and not drone_state.is_flying:
            drone_state.is_flying = True
        elif not armed and drone_state.is_flying:
            drone_state.is_flying = False
            drone_state.flight_count += 1

        # Get current position
        position = await drone.telemetry.position()
        
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

        data = {
            "drone_id": args.drone_id,
            "latitude": position.latitude_deg,
            "longitude": position.longitude_deg,
            "absolute_altitude_m": position.absolute_altitude_m,
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "battery_percentage": battery_percent,
            "flight_mode": current_mode,
            "is_online": True,
            "flight_count": drone_state.flight_count,
            "emergency_status": is_emergency,
            "emergency_reasons": emergency_reasons,
            "trajectory": drone_state.trajectory
        }
        
        topic = f"drone/{args.drone_id}/telemetry"
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