from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    mqtt_host: str = Field("mosquitto", alias="MQTT_HOST")
    mqtt_port: int = Field(1883, alias="MQTT_PORT")
    mqtt_topic: str = Field("drone/+/telemetry", alias="MQTT_TOPIC")
    mqtt_reconnect_delay: int = Field(5, alias="MQTT_RECONNECT_DELAY")
    postgres_user: str = Field("postgres", alias="POSTGRES_USER")
    postgres_password: str = Field("postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field("telemetry", alias="POSTGRES_DB")
    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    stale_after_sec: int = Field(10, alias="STALE_AFTER_SEC")
    offline_after_sec: int = Field(30, alias="OFFLINE_AFTER_SEC")
    max_drones: int = Field(200, alias="MAX_DRONES")
    ingest_max_concurrency: int = Field(10, alias="INGEST_MAX_CONCURRENCY")
    ingest_backlog_max: int = Field(100, alias="INGEST_BACKLOG_MAX")
    emergency_battery_pct: float = Field(5.0, alias="EMERGENCY_BATTERY_PCT")
    ws_push_hz: float = Field(5.0, alias="WS_PUSH_HZ")

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()