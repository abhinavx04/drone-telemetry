import asyncio
import argparse
import logging
from mavsdk import System
# Correct import for paho-mqtt v2+
from paho.mqtt import client as mqtt_module

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def on_connect(client, userdata, flags, rc, properties):
    logging.info(f"Connected to MQTT Broker with result code {rc}")

async def main():
    parser = argparse.ArgumentParser(description="Connect to a drone and publish telemetry.")
    parser.add_argument('--port', type=int, default=14540, help='Port to listen on.')
    parser.add_argument('--drone-id', required=True, help='Unique ID for the drone.')
    parser.add_argument('--mqtt-host', default='localhost', help='MQTT broker host.')
    parser.add_argument('--simulator-host', default='127.0.0.1', help='Host IP of the simulator.')
    args = parser.parse_args()

    # Use the new callback API version
    mqtt_client = mqtt_module.Client(callback_api_version=mqtt_module.CallbackAPIVersion.VERSION2, client_id=f"mavsdk-{args.drone_id}")
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(args.mqtt_host, 1883, 60)
    mqtt_client.loop_start()

    drone = System()

    # Real drone mode: listen for a vehicle sending MAVLink to this port.
    # Use udpin so the vehicle can initiate the connection.
    logging.info(f"Waiting for drone to connect at udpin://0.0.0.0:{args.port}...")
    await drone.connect(system_address=f"udpin://0.0.0.0:{args.port}")

    logging.info("Drone connected!")

    async for position in drone.telemetry.position():
        payload = f'{{"latitude": {position.latitude_deg}, "longitude": {position.longitude_deg}, "altitude": {position.absolute_altitude_m}}}'
        topic = f"drone/{args.drone_id}/telemetry"
        mqtt_client.publish(topic, payload)
        logging.info(f"Published to {topic}: {payload}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Script failed: {e}")