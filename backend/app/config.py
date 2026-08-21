from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MTPULSE_")
    app_name: str = "MT Pulse API"
    database_url: str = "postgresql+psycopg://mtpulse:mtpulse@localhost:5432/mtpulse"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
