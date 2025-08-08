# Drone Telemetry Pipeline

This is a full-stack, multi-drone telemetry pipeline using FastAPI, MQTT, TimescaleDB, and Docker Compose. It allows for real-time telemetry data ingestion, storage, and API exposure for multiple drones.

## Project Overview

The Drone Telemetry Pipeline is designed to efficiently manage and process telemetry data from multiple drones. It leverages modern technologies to ensure scalability and reliability.

- **backend/**: FastAPI backend (ingests telemetry, stores in DB, exposes API)
- **mavsdk/**: MAVSDK Python app (subscribes to drone, publishes telemetry to MQTT)
- **mosquitto/**: MQTT broker config
- **docker-compose.yml**: Orchestrates the stack

## Prerequisites

- Docker
- Docker Compose
- Python 3.8+

## Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```bash
   cd drone-telemetry
   ```
3. Edit the `.env` file as needed to configure environment variables.
4. Build and start the services:
   ```bash
   docker-compose up --build
   ```

## Usage

- Access the FastAPI backend at `http://localhost:8000`
- Connect to the MQTT broker at `mqtt://localhost:1883`
- Access TimescaleDB at `localhost:5432`

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Ports

- FastAPI: 8000
- MQTT: 1883
- TimescaleDB: 5432
