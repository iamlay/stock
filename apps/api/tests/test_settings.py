from app.settings import Settings


def test_postgres_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgres://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"

    settings = Settings(database_url="postgresql://user:pass@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_quoted_url_is_cleaned() -> None:
    settings = Settings(database_url=' "postgresql://user:pass@host:5432/db" ')
    assert settings.database_url == "postgresql+psycopg://user:pass@host:5432/db"


def test_unresolved_reference_is_rejected() -> None:
    try:
        Settings(database_url="${{Postgres.DATABASE_URL}}")
    except ValueError as exc:
        assert "unresolved" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_explicit_psycopg_scheme_is_kept() -> None:
    url = "postgresql+psycopg://user:pass@host:5432/db?sslmode=require"
    assert Settings(database_url=url).database_url == url


def test_cors_origin_regex_is_optional() -> None:
    settings = Settings(cors_origin_regex=r"https://.*\.vercel\.app")
    assert settings.cors_origin_regex == r"https://.*\.vercel\.app"


def test_email_provider_configuration() -> None:
    assert not Settings(email_provider="smtp").email_configured

    smtp = Settings(
        email_provider="smtp",
        smtp_host="smtp.example.com",
        smtp_from="hi@example.com",
    )
    assert smtp.email_configured

    resend = Settings(
        email_provider="resend",
        resend_api_key="re_test",
        email_from="StockLab <hi@example.com>",
    )
    assert resend.email_configured
    assert resend.from_address == "StockLab <hi@example.com>"

    brevo = Settings(email_provider="brevo", brevo_api_key="brevo_test")
    assert not brevo.email_configured
