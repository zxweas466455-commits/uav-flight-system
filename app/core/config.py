from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/uav_flight_db"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/uav_flight_db"
    app_name: str = "UAV Flight Management System"
    debug: bool = True
    secret_key: str = "change-me"
    airspace_api_url: str = ""
    airspace_api_key: str = ""
    telemetry_interval_seconds: int = 5

    class Config:
        env_file = ".env"

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/uav_flight_db"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/uav_flight_db"
    app_name: str = "UAV Flight Management System"
    debug: bool = False
    sql_echo: bool = False          # ← добавить
    secret_key: str = "change-me"
    airspace_api_url: str = ""
    airspace_api_key: str = ""
    telemetry_interval_seconds: int = 5

    class Config:
        env_file = ".env"
@lru_cache()
def get_settings() -> Settings:
    return Settings()