import asyncio
import random
import time
import logging
from pymavlink import mavutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [SIMULATOR] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

async def run_simulator():
    # Give the MAVSDK client a moment to start listening
    await asyncio.sleep(5)

    try:
        # Connect outbound to mavsdk-drone1's UDP port. This is where the simulator SENDS data.
        master = mavutil.mavlink_connection('udpout:mavsdk-drone1:14540', dialect='ardupilotmega')
        logging.info("Simulator connected. Sending data to mavsdk-drone1:14540")
    except Exception as e:
        logging.error(f"Failed to connect simulator: {e}")
        return

    # Initial position (latitude/longitude in degrees * 1e7, altitude in mm)
    lat = int(40.7128 * 1e7)
    lon = int(-74.0060 * 1e7)
    alt = 100000  # 100m in mm

    logging.info("Simulator is now sending telemetry...")
    while True:
        try:
            # Send heartbeat (required to keep the connection alive)
            master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )

            # Send global position
            master.mav.global_position_int_send(
                int(time.time() * 1000),  # time_boot_ms
                lat,
                lon,
                alt, # alt
                0, 0, 0, # vx, vy, vz
                0 # hdg
            )
            logging.info(f"Sent position: Lat {lat / 1e7:.4f}, Lon {lon / 1e7:.4f}")

            # Slightly move the drone for the next update
            lat += int(random.uniform(-100, 100))
            lon += int(random.uniform(-100, 100))

            await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"Error during simulation loop: {e}")
            await asyncio.sleep(5) # Wait before retrying

if __name__ == "__main__":
    try:
        asyncio.run(run_simulator())
    except Exception as e:
        logging.error(f"Simulator crashed: {e}")