# Multi-stage Dockerfile for Fleet Health Exporter
# Uses python:3.11-slim as base (spec requirement)
# Exposes port 8000 (Prometheus HTTP server)
# Runs as non-root user uid 1000

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim AS runtime

RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --no-create-home appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY fleet_exporter.py health_calculator.py datadog_bridge.py ./

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    METRICS_PORT=8000 \
    SCRAPE_INTERVAL=30 \
    ENVIRONMENT=prod

USER appuser
EXPOSE 8000

# HEALTHCHECK polls /metrics every 30s as required by spec
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/metrics')"

ENTRYPOINT ["python", "fleet_exporter.py"]
