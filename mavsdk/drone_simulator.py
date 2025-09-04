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
    await asyncio.sleep(5)

    try:
        master = mavutil.mavlink_connection('udpout:mavsdk-drone1:14540', dialect='ardupilotmega')
        logging.info("Simulator connected. Sending data to mavsdk-drone1:14540")
    except Exception as e:
        logging.error(f"Failed to connect simulator: {e}")
        return

    lat = int(40.7128 * 1e7)
    lon = int(-74.0060 * 1e7)
    alt = 100000

    # FIX: Use a robust method to calculate boot time
    start_time = time.time()
    logging.info("Simulator is now sending telemetry...")
    while True:
        try:
            # Calculate milliseconds since script start
            time_boot_ms = int((time.time() - start_time) * 1000)

            master.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_QUADROTOR,
                mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                0, 0, 0
            )

            master.mav.global_position_int_send(
                time_boot_ms, # Guaranteed to be a positive integer
                lat,
                lon,
                alt,
                0, # relative_alt
                0, # vx
                0, # vy
                0, # vz
                0  # hdg
            )
            logging.info(f"Sent position: Lat {lat / 1e7:.4f}, Lon {lon / 1e7:.4f}")

            lat += int(random.uniform(-100, 100))
            lon += int(random.uniform(-100, 100))

            await asyncio.sleep(1)

        except Exception as e:
            logging.error(f"Error during simulation loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(run_simulator())
    except Exception as e:
        logging.error(f"Simulator crashed: {e}")