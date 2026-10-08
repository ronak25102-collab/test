FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock /app/
COPY backend /app/backend
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
ENV PYTHONPATH=/app/backend/src
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/backend
CMD ["uvicorn", "signal_research.main:app", "--host", "0.0.0.0", "--port", "8000"]
