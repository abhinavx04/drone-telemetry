import asyncio
import random
import logging
from mavsdk.server import Server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [SIMULATOR] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

async def run_simulator():
    # Add a small delay to ensure the mavsdk-drone1 service is ready
    await asyncio.sleep(2)

    server = Server(address="mavsdk-drone1", port=14540)
    await server.start()
    logging.info("Simulator server started. Sending data to mavsdk-drone1:14540")

    lat, lon, alt = 40.7128, -74.0060, 100.0
    
    logging.info("Simulator is now sending telemetry...")
    while True:
        lat += random.uniform(-0.0001, 0.0001)
        lon += random.uniform(-0.0001, 0.0001)
        await server.telemetry.set_position(lat, lon, alt, 0)
        logging.info(f"Sent position update (Lat: {lat:.4f}, Lon: {lon:.4f})")
        await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(run_simulator())
    except Exception as e:
        logging.error(f"Simulator crashed: {e}")
