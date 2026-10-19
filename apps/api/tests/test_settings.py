from app.settings import Settings


def test_postgres_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgres://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"

    settings = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_explicit_psycopg_scheme_is_kept() -> None:
    url = "postgresql+psycopg://user:pass@host:5432/db?sslmode=require"
    assert Settings(database_url=url).database_url == url


def test_cors_origin_regex_is_optional() -> None:
    settings = Settings(cors_origin_regex=r"https://.*\.vercel\.app")
    assert settings.cors_origin_regex == r"https://.*\.vercel\.app"
