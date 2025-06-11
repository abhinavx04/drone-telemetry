from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Example settings
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "telemetry"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883

    class Config:
        env_file = ".env"

settings = Settings()