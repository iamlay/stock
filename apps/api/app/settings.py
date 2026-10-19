from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, overridable via STOCKLAB_* env vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="STOCKLAB_",
        extra="ignore",
    )

    app_name: str = "StockLab API"
    version: str = "0.1.0"
    env: str = "local"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    database_url: str = "postgresql+psycopg://stocklab:stocklab@127.0.0.1:5432/stocklab"
    data_start_date: str = "2016-01-01"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
