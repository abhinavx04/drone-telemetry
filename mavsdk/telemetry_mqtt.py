import asyncio
import argparse
import json
from mavsdk import System
import paho.mqtt.client as mqtt

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

    async for telemetry in drone.telemetry.position():
        data = {
            "drone_id": args.drone_id,
            "latitude": telemetry.latitude_deg,
            "longitude": telemetry.longitude_deg,
            "absolute_altitude_m": telemetry.absolute_altitude_m,
            "timestamp": telemetry.timestamp_us
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