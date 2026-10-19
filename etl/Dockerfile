FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY apps/api/pyproject.toml ./
COPY apps/api/app ./app
COPY apps/api/alembic.ini ./
COPY apps/api/alembic ./alembic
COPY etl ./etl

RUN pip install .

CMD ["sh", "-c", "alembic upgrade head && python -m etl.cli daily"]
