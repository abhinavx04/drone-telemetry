# Drone Telemetry

FastAPI service that ingests drone telemetry over **HTTP** and **MQTT**, stores time-series rows in **PostgreSQL**, and exposes a small **REST** surface for dashboards.

---

## Table of contents

1. [Architecture](#architecture)
2. [Quick start](#quick-start)
3. [Required configuration](#required-configuration)
4. [Telemetry payload contract](#telemetry-payload-contract-must-match)
5. [API reference](#api-reference)
6. [Docker Compose services](#docker-compose-services)
7. [Local development](#local-development)
8. [Security](#security)

---

## Architecture

| Path | Responsibility |
|------|------------------|
| HTTP `POST /telemetry/` | Accept validated JSON; persist one row per message |
| MQTT subscriber | Connect to broker, subscribe to topic, parse JSON → same schema as HTTP |
| PostgreSQL | Table `telemetry` — composite key `(drone_id, timestamp)` |
| `GET /api/v1/drones` | Latest row per `drone_id` (`DISTINCT ON` query) |
| `GET /telemetry/{drone_id}` | Recent rows for one drone (paginated by `limit`) |

---

## Quick start

```bash
docker compose up -d --build
```

| Endpoint | URL |
|----------|-----|
| API root | http://localhost:8000 |
| Interactive docs (Swagger) | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

---

## Required configuration

All settings are loaded from **environment variables** (and optional `backend/.env`). These are the parameters you **must** set correctly for each environment.

### Database (PostgreSQL)

| Parameter | Environment variable | Default in code | Typical Docker value |
|-----------|----------------------|-----------------|----------------------|
| Host | `POSTGRES_HOST` | `db` | `db` (Compose service name) |
| Port | `POSTGRES_PORT` | `5432` | `5432` |
| Database name | `POSTGRES_DB` | `telemetry` | `drone_telemetry` (see Compose) |
| User | `POSTGRES_USER` | `postgres` | `postgres` |
| Password | `POSTGRES_PASSWORD` | `postgres` | must match DB container |

**Important:** `POSTGRES_DB` in the app **must match** the database created by the Postgres container. If Compose uses `POSTGRES_DB=drone_telemetry`, set the same for the backend.

### MQTT (subscriber)

| Parameter | Environment variable | Default | Role |
|-----------|----------------------|---------|------|
| Broker host | `MQTT_HOST` | `mosquitto` | TCP host (Compose: service `mosquitto`) |
| Broker port | `MQTT_PORT` | `1883` | TCP port |
| Subscribe topic | `MQTT_TOPIC` | `drone/+/telemetry` | Wildcard `+` = one segment per drone id |

The listener starts on app startup and **retries every 5 seconds** on connection failure. Payloads **must** be valid JSON matching [`TelemetryIn`](#telemetry-payload-contract-must-match).

### Logging

| Parameter | Environment variable | Default |
|-----------|----------------------|---------|
| Log level | `LOG_LEVEL` | `INFO` |

---

## Telemetry payload contract (must match)

Used by:

- **`POST /telemetry/`** (JSON body)
- **MQTT** messages on `MQTT_TOPIC` (UTF-8 JSON)

Validation is defined in `backend/app/schemas.py` (`TelemetryIn`).

| Field | Type | Required | Rules |
|-------|------|----------|--------|
| `drone_id` | string | yes | max length **50** |
| `latitude` | number | yes | degrees |
| `longitude` | number | yes | degrees |
| `timestamp` | int or datetime or ISO string | yes | Stored as **Unix seconds** (int) after validation |
| `absolute_altitude_m` | number or null | no | meters |
| `battery_percentage` | number or null | no | |
| `flight_mode` | string or null | no | If set, must be exactly **`manual`**, **`atti`**, or **`rth`** |
| `is_online` | boolean or null | no | defaults to **true** |

**Example (MQTT / HTTP body):**

```json
{
  "drone_id": "alpha-1",
  "latitude": 37.7749,
  "longitude": -122.4194,
  "absolute_altitude_m": 120.5,
  "timestamp": 1730000000,
  "battery_percentage": 87.0,
  "flight_mode": "manual",
  "is_online": true
}
```

---

## API reference

Base URL: `http://<host>:8000` (default **8000**).

### Versioned (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/drones` | Latest telemetry **per** `drone_id` (fleet list) |

### Unversioned (legacy / simple clients)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{ "status": "ok" }` |
| `GET` | `/` | Welcome message |
| `POST` | `/telemetry/` | Create one telemetry row (**201**) |
| `GET` | `/telemetry/{drone_id}` | Recent points for `drone_id`; query param **`limit`** (default **10**) |

Open **`/docs`** for request/response schemas and try-it-out.

---

## Docker Compose services

| Service | Image / build | Host ports | Notes |
|---------|---------------|------------|--------|
| `mosquitto` | `eclipse-mosquitto:2` | **1883** | Config: `./mosquitto/config` |
| `db` | `timescale/timescaledb:latest-pg14` | **5432** | Credentials via Compose `environment` |
| `backend` | `build: ./backend` | **8000** | Depends on `db`, `mosquitto` |
| `simulator` | `./mavsdk` (`Dockerfile.simulator`) | — | Local SITL-style testing (builds with stack) |
| `mavsdk-drone1` | `./mavsdk` (`Dockerfile.mavsdk`) | — | Publishes to MQTT; uses UDP **14540** toward `simulator` |

Persistent DB data: named volume `postgres_data`.

If you only need API + DB + broker, remove or disable the `simulator` / `mavsdk-drone1` services in `docker-compose.yml` so they are not built on every `up`.

---

## Local development

1. Start only infrastructure:  
   `docker compose up -d db mosquitto`
2. Create a venv, install `backend/requirements.txt`, set `POSTGRES_HOST=localhost` and matching `POSTGRES_DB` / password.
3. Run from `backend/`:  
   `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

Point a **React/Vite** frontend (see `frontend/`) at the API base URL via your env (e.g. `VITE_API_URL`).

---

## Security

- **CORS** is set to allow **all origins** — restrict before production.
- There is **no authentication** on these endpoints in this codebase — use a reverse proxy, VPN, or add auth as needed.

---

## Repository layout

```
backend/           # FastAPI app (`app.main:app`)
docker-compose.yml # db + mosquitto + backend (+ optional mavsdk profile)
frontend/          # Vite + React demo client
mosquitto/         # Broker configuration
mavsdk/            # Optional simulator / MAVSDK tooling
```

Add a **`LICENSE`** file when you publish the project publicly.
