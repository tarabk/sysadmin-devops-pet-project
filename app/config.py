from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = "postgresql+psycopg://taskboard_user:change_me@127.0.0.1:5432/taskboard"
    cors_origins: str = "http://127.0.0.1:8080,http://localhost:8080"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
