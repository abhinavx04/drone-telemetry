from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    mqtt_host: str = Field("localhost", env="MQTT_HOST")
    mqtt_port: int = Field(1883, env="MQTT_PORT")
    mqtt_topic: str = Field("drone/+/telemetry", env="MQTT_TOPIC")
    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_name: str = Field("drone_telemetry", env="DB_NAME")
    db_user: str = Field("postgres", env="DB_USER")
    db_password: str = Field("example", env="DB_PASSWORD")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"

settings = Settings()