from functools import lru_cache

from pydantic import field_validator
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
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3100,http://127.0.0.1:3100"
    )
    cors_origin_regex: str = ""
    database_url: str = "postgresql+psycopg://stocklab:stocklab@127.0.0.1:5432/stocklab"
    data_start_date: str = "2016-01-01"
    jwt_secret: str = "dev-only-change-me-please-32-bytes-min"
    jwt_ttl_minutes: int = 720
    otp_secret: str = "dev-only-change-me-please-32-bytes-min"
    auth_dev_mode: bool = True
    sms_provider: str = "none"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    email_provider: str = "smtp"
    email_from: str = ""
    resend_api_key: str = ""
    brevo_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    guest_daily_limit: int = 20
    free_daily_limit: int = 50

    @property
    def from_address(self) -> str:
        return self.email_from or self.smtp_from

    @property
    def email_configured(self) -> bool:
        provider = self.email_provider.strip().lower()
        if provider == "smtp":
            return bool(self.smtp_host and self.from_address)
        if provider == "resend":
            return bool(self.resend_api_key and self.from_address)
        if provider == "brevo":
            return bool(self.brevo_api_key and self.from_address)
        return False

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Accept Railway/Heroku URLs and reject unresolved reference strings."""
        if not isinstance(value, str):
            return value
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1].strip()
        if "${{" in value or value == "":
            raise ValueError(
                "STOCKLAB_DATABASE_URL is empty or contains an unresolved "
                "Railway reference; use Add Reference or a literal URL"
            )
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value[len("postgresql://") :]
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
