FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/backend

COPY backend/pyproject.toml README.md /srv/backend/
COPY backend/app /srv/backend/app

RUN pip install --no-cache-dir .

EXPOSE 8001

# Default binds loopback; override APP_HOST/APP_PORT behind a trusted proxy.
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"]
