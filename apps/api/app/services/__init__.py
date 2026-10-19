"""Read-side services used by both the API and the ETL CLI."""

from app.services.status import collect_status

__all__ = ["collect_status"]
