FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/backend

COPY backend/pyproject.toml README.md /srv/backend/
COPY backend/app /srv/backend/app
# Alembic schema + app package: the BFF runs pending migrations at startup when
# DATABASE_URL is set (audit persistence and database users, B9).
COPY backend/alembic.ini /srv/backend/alembic.ini
COPY backend/migrations /srv/backend/migrations

RUN pip install --no-cache-dir .

EXPOSE 8001

# Default binds loopback; override APP_HOST/APP_PORT behind a trusted proxy.
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"]
