FROM python:3.11-slim AS base

WORKDIR /app

# System dependencies for geospatial processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash spikeeo
RUN mkdir -p /app/data /app/pretrained /app/models && chown -R spikeeo:spikeeo /app

COPY pyproject.toml README.md ./
COPY spikeeo/ ./spikeeo/
COPY examples/ ./examples/

# Install API dependencies
RUN pip install --no-cache-dir -e ".[api]"

USER spikeeo

ENV SPIKEEO_APP_HOST=0.0.0.0
ENV SPIKEEO_APP_PORT=8000
ENV SPIKEEO_LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["python", "-m", "spikeeo.api.server"]
