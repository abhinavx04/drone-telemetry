import asyncio
import argparse
import logging
from mavsdk import System
import paho.mqtt.client as mqtt

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

    mqtt_client = mqtt.Client(client_id=f"mavsdk-{args.drone_id}")
    mqtt_client.on_connect = on_connect
    try:
        mqtt_client.connect(args.mqtt_host, args.mqtt_port, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logging.error(f"Could not connect to MQTT broker. Error: {e}")
        return

    drone = System(mavsdk_server_address='localhost', port=args.port)

    logging.info(f"Starting telemetry stream for {args.drone_id}. Listening on UDP port {args.port}...")
    
    # This loop will now correctly start the server and wait for a connection.
    async for position in drone.telemetry.position():
        logging.info(f"Simulator connected to {args.drone_id}!") # This will print once connected
        
        # This inner loop will run as long as telemetry is being received
        while True:
            lat = position.latitude_deg
            lon = position.longitude_deg
            alt = position.absolute_altitude_m
            
            payload = f'{{"latitude": {lat}, "longitude": {lon}, "altitude": {alt}}}'
            topic = f"drone/{args.drone_id}/telemetry"
            
            mqtt_client.publish(topic, payload)
            logging.info(f"Published to {topic}: {payload}")
            
            # Wait for the next position update
            await asyncio.sleep(1)
            position = await drone.telemetry.position().__anext__()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"MAVSDK script failed: {e}")
