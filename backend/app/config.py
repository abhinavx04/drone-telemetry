from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    mqtt_host: str = Field("mosquitto", alias="MQTT_HOST")
    mqtt_port: int = Field(1883, alias="MQTT_PORT")
    mqtt_topic: str = Field("drone/+/telemetry", alias="MQTT_TOPIC")
    mqtt_reconnect_delay: int = Field(5, alias="MQTT_RECONNECT_DELAY")
    publish_rate_hz: float = Field(5.0, alias="PUBLISH_RATE_HZ")
    summary_rate_hz: float = Field(1.0, alias="SUMMARY_RATE_HZ")
    ingest_rate_hz: float = Field(0.0, alias="INGEST_RATE_HZ")  # 0 = unlimited
    udp_bind_host: str = Field("0.0.0.0", alias="UDP_BIND_HOST")
    udp_bind_start_port: int = Field(14540, alias="UDP_BIND_START_PORT")
    udp_bind_end_port: int = Field(14639, alias="UDP_BIND_END_PORT")
    udp_recv_buffer_bytes: int = Field(8 * 1024 * 1024, alias="UDP_RECV_BUFFER_BYTES")
    ingest_enable_mqtt_listener: bool = Field(False, alias="INGEST_ENABLE_MQTT_LISTENER")
    ingest_enable_http_post: bool = Field(False, alias="INGEST_ENABLE_HTTP_POST")

    drone_id: str = Field("drone_alpha", alias="DRONE_ID")
    drone_label: str = Field("PX4_QUAD_X", alias="DRONE_LABEL")
    mavsdk_url: str = Field("udp://0.0.0.0:14540", alias="MAVSDK_URL")
    mavsdk_connect_retry_s: int = Field(3, alias="MAVSDK_CONNECT_RETRY_SEC")
    mavsdk_degraded_after_s: int = Field(5, alias="MAVSDK_DEGRADED_AFTER_SEC")
    mavsdk_disconnected_after_s: int = Field(15, alias="MAVSDK_DISCONNECTED_AFTER_SEC")
    postgres_user: str = Field("postgres", alias="POSTGRES_USER")
    postgres_password: str = Field("postgres", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field("telemetry", alias="POSTGRES_DB")
    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    stale_after_sec: int = Field(5, alias="STALE_AFTER_SEC")
    offline_after_sec: int = Field(30, alias="OFFLINE_AFTER_SEC")
    max_drones: int = Field(200, alias="MAX_DRONES")
    ingest_max_concurrency: int = Field(10, alias="INGEST_MAX_CONCURRENCY")
    ingest_backlog_max: int = Field(100, alias="INGEST_BACKLOG_MAX")
    emergency_battery_pct: float = Field(5.0, alias="EMERGENCY_BATTERY_PCT")
    ws_push_hz: float = Field(5.0, alias="WS_PUSH_HZ")
    ingest_debug_stats: bool = Field(True, alias="INGEST_DEBUG_STATS")
    gc_interval_sec: int = Field(300, alias="GC_INTERVAL_SEC")
    gc_offline_after_sec: int = Field(3600, alias="GC_OFFLINE_AFTER_SEC")

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()