# ─────────────────────────────────────────────────────────
# Stage 1: Build dependencies
# ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install build tools needed for native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ gdal-bin libgdal-dev libgeos-dev libproj-dev \
        libffi-dev curl git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install pip + hatch
RUN pip install --no-cache-dir --upgrade pip hatchling

# Copy dependency definitions first for layer caching
COPY pyproject.toml .
COPY carbonsnn/__init__.py carbonsnn/

# Install all dependencies into a staging prefix
RUN pip install --no-cache-dir --prefix=/install ".[postgresql]"


# ─────────────────────────────────────────────────────────
# Stage 2: Runtime image
# ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="CarbonSNN Team <contact@carbonsnn.io>"
LABEL description="CarbonSNN – satellite deforestation detection and carbon MRV SaaS"
LABEL version="0.1.0"

# Runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev libgeos-dev libproj-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 carbonsnn
WORKDIR /app

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source
COPY --chown=carbonsnn:carbonsnn . .

# Create required directories with proper ownership
RUN mkdir -p data models/weights logs && \
    chown -R carbonsnn:carbonsnn data models logs

USER carbonsnn

# Environment defaults (override via docker-compose or -e flags)
ENV APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: start the FastAPI server
CMD ["python", "-m", "uvicorn", "carbonsnn.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
