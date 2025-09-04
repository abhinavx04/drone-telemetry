import asyncio
import argparse
import logging
from mavsdk import System
import paho.mqtt.client as mqtt

# --- Setup logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT Broker!")
    else:
        logging.error(f"Failed to connect to MQTT, return code {rc}\n")

async def main():
    parser = argparse.ArgumentParser(description="Listen for a simulated drone and publish telemetry to MQTT.")
    parser.add_argument('--port', type=int, default=14540, help='Port to listen on.')
    parser.add_argument('--drone-id', required=True, help='Unique ID for the drone.')
    parser.add_argument('--mqtt-host', default='localhost', help='MQTT broker host.')
    parser.add_argument('--mqtt-port', type=int, default=1883, help='MQTT broker port.')
    args = parser.parse_args()

    # --- MQTT Client Setup ---
    mqtt_client = mqtt.Client(client_id=f"mavsdk-{args.drone_id}")
    mqtt_client.on_connect = on_connect
    try:
        mqtt_client.connect(args.mqtt_host, args.mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logging.error(f"Could not connect to MQTT broker. Error: {e}")
        return

    # --- MAVSDK Drone Connection ---
    drone = System()
    connection_string = f"udp://:{args.port}"
    await drone.connect(system_address=connection_string)

    logging.info(f"Opened UDP port {args.port}. Waiting for simulator to connect...")

    # Wait for the drone (our simulator) to connect
    async for state in drone.core.connection_state():
        if state.is_connected:
            logging.info(f"Simulator connected to {args.drone_id}!")
            break

    # Start publishing telemetry
    logging.info(f"Starting telemetry stream for {args.drone_id}")
    async for position in drone.telemetry.position():
        lat = position.latitude_deg
        lon = position.longitude_deg
        alt = position.absolute_altitude_m
        
        payload = f'{{"latitude": {lat}, "longitude": {lon}, "altitude": {alt}}}'
        topic = f"drone/{args.drone_id}/telemetry"
        
        mqtt_client.publish(topic, payload)
        logging.info(f"Published to {topic}: {payload}")
        # No sleep needed here, as the loop is driven by incoming telemetry

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"MAVSDK script failed: {e}")