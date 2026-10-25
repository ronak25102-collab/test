FROM node:22-alpine AS frontend-build
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY --from=frontend-build /web/dist ./frontend/dist
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    FRONTEND_DIST_DIR=/app/frontend/dist \
    PIPELINE_MODE=precomputed \
    AUTO_START_WORKER=true
EXPOSE 10000
CMD ["/bin/sh", "-c", "alembic -c /app/backend/alembic.ini upgrade head && exec uvicorn signal_research.main:app --host 0.0.0.0 --port \"${PORT:-10000}\" --workers 1"]
