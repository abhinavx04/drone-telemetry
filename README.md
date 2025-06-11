# Drone Telemetry Pipeline

This is a full-stack, multi-drone telemetry pipeline using FastAPI, MQTT, TimescaleDB, and Docker Compose.  
- **backend/**: FastAPI backend (ingests telemetry, stores in DB, exposes API)  
- **mavsdk/**: MAVSDK Python app (subscribes to drone, publishes telemetry to MQTT)  
- **mosquitto/**: MQTT broker config  
- **docker-compose.yml**: Orchestrates the stack  

## Setup

1. `git clone ...`
2. Edit `.env` as needed
3. `docker-compose up --build`

## Ports

- FastAPI: 8000
- MQTT: 1883
- TimescaleDB: 5432
