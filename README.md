# Drone Telemetry

**PX4-oriented drone telemetry:** MAVLink UDP ingest → **FastAPI** (**REST** + **WebSocket**) → **PostgreSQL**, with per-flight history, optional **MQTT**, and **PX4 ULog** upload/storage.

---

## Quick start

```bash
docker compose up -d --build
```

| | |
|---|---|
| API | http://localhost:8000 |
| Docs | http://localhost:8000/docs |
| Health | `GET /api/v1/health` |

ULogs land in `./data/ulogs` (mounted in Compose). Optional SITL stack: `docker compose --profile sim up -d` (uses UDP **14540** — don’t collide with prod).

---

## What’s in the repo

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI app (async SQLAlchemy + asyncpg, pymavlink ingest) |
| `docker-compose.yml` | Backend, PostgreSQL (Timescale image), Mosquitto, UDP **14540–14639** |
| `mavsdk/` | Simulator / MAVSDK helpers (optional `sim` profile) |
| `frontend/` | Small React + Vite demo UI |

---

## Stack (high level)

Python 3.11 · FastAPI · Uvicorn · SQLAlchemy 2 · asyncpg · PostgreSQL · pymavlink · asyncio-mqtt · Docker Compose

---

## Configuration

Backend reads env vars (see `backend/app/config.py`). Compose sets things like `STALE_AFTER_SEC`, `WS_PUSH_HZ`, `POSTGRES_*`, `ULOG_STORAGE_DIR`. Override in `docker-compose.yml` or your own `.env` for local runs.

---

## API

Versioned routes live under **`/api/v1`** — drones, latest telemetry, WebSocket stream, flights, paginated flight telemetry, ULog list/upload, CSV/JSON import. Full list and schemas: **`/docs`** (Swagger).

---

## Security

CORS is open by default; there is no app-level auth in this codebase. Lock down for production (gateway, VPN, or add auth).

---

## License

Add a root `LICENSE` when you publish.
