FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --upgrade pip

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh && pip install .

EXPOSE 8080

# Cloud Run injects PORT=8080; entrypoint runs migrations (when configured) then uvicorn.
CMD ["./entrypoint.sh"]
