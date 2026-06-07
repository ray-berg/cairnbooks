FROM python:3.12-slim

WORKDIR /app

# Install system deps (curl used in healthcheck)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cache-friendly: copy manifest first)
COPY pyproject.toml ./
RUN touch README.md \
    && mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf app README.md

# Copy application source
COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
