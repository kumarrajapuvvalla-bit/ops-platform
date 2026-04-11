"""api_server.py — FastAPI layer for the Fleet Health Exporter.

Replaces the bare prometheus_client.start_http_server() with a proper
FastAPI application that adds:

  1. JWT authentication (/token + Bearer middleware)
  2. API versioning (/v1/fleet/score vs /v2/fleet/score)
  3. Idempotency keys on score-override endpoint
  4. Cursor-based pagination on /v1/fleet/history
  5. Outbound webhooks with HMAC signing
  6. X-Request-ID correlation ID middleware

The exporter's Prometheus metrics are still exposed at /metrics
(scraped by prometheus_client's built-in WSGI app via a separate thread).

Run via: uvicorn exporter.api_server:app --port 8000
"""

import logging
import time
import uuid
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field

from api_auth import (
    FAKE_CLIENTS, TOKEN_TTL_MINUTES,
    TokenRequest, TokenResponse,
    create_access_token, get_current_client,
)
from api_history import paginate_history, record_score
from api_idempotency import get_cached, set_cached
from api_webhooks import (
    WebhookRegistration, WebhookRegistrationResponse,
    deliver_score_event, list_urls, register_url,
)

log = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Fleet Health API",
    description=(
        "Advanced API layer for the Self-Healing Cloud Operations Platform.\n\n"
        "Features:\n"
        "- JWT authentication (client credentials)\n"
        "- API versioning: /v1 (score) vs /v2 (score + breakdown + recommendations)\n"
        "- Idempotency keys on score overrides\n"
        "- Cursor-based pagination on score history\n"
        "- Outbound webhooks with HMAC-SHA256 signing\n"
        "- X-Request-ID correlation ID throughout"
    ),
    version="2.0.0",
)


# ── Models ────────────────────────────────────────────────────────────────────
class FleetScoreV1(BaseModel):
    """V1 response — score and SLO compliance only."""
    score: float
    environment: str
    cluster: str
    slo_compliant: bool
    collected_at: int


class ServiceBreakdown(BaseModel):
    name: str
    health_ratio: float
    status: str  # healthy | degraded | unknown


class FleetScoreV2(FleetScoreV1):
    """V2 response — adds per-service breakdown + auto-recommendations."""
    degraded_services: list[str]
    breach_reason: Optional[str]
    service_breakdown: list[ServiceBreakdown]
    recommendations: list[str]
    api_version: str = "v2"


class ScoreOverride(BaseModel):
    """Manual score override for testing/demo purposes."""
    score: float = Field(..., ge=0.0, le=100.0)
    reason: str = Field(..., min_length=3)
    environment: str = "dev"
    cluster: str = "ops-platform"


# ── In-memory latest score cache (set by background collector) ───────────────────
_latest: dict = {
    "score": 100.0,
    "environment": "dev",
    "cluster": "ops-platform",
    "degraded_services": [],
    "breach_reason": None,
    "breakdown": [],
    "collected_at": 0,
}


def update_latest_score(
    score: float,
    environment: str,
    cluster: str,
    degraded_services: list,
    breach_reason: Optional[str],
    breakdown: list,
) -> None:
    """Called by fleet_exporter.py after each collection cycle."""
    _latest.update(
        score=score,
        environment=environment,
        cluster=cluster,
        degraded_services=degraded_services,
        breach_reason=breach_reason,
        breakdown=breakdown,
        collected_at=int(time.time()),
    )
    record_score(score, environment, cluster, degraded_services, breach_reason)


# ── Middleware: correlation ID + logging ───────────────────────────────────────────
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Request-ID"] = request_id
    log.info(
        "method=%s path=%s status=%d duration=%.3fs request_id=%s",
        request.method, request.url.path,
        response.status_code, duration, request_id,
    )
    return response


# ── Ops routes ───────────────────────────────────────────────────────────────────
@app.get("/healthz", tags=["ops"])
async def health():
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def ready():
    age = int(time.time()) - _latest["collected_at"]
    if _latest["collected_at"] > 0 and age > 180:
        raise HTTPException(status_code=503, detail=f"Last collection {age}s ago")
    return {"status": "ready", "last_collection_age_seconds": age}


@app.get("/metrics", tags=["ops"])
async def metrics():
    """Prometheus scrape endpoint."""
    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Auth routes ───────────────────────────────────────────────────────────────────
@app.post("/token", response_model=TokenResponse, tags=["auth"])
async def issue_token(body: TokenRequest):
    """
    Client credentials token endpoint.

    Pre-configured clients: `grafana-agent`, `alertmanager`, `ops-dashboard`.
    Returns a HS256 JWT valid for 30 minutes.
    """
    expected = FAKE_CLIENTS.get(body.client_id)
    if not expected or expected != body.client_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    return TokenResponse(
        access_token=create_access_token(body.client_id),
        expires_in=TOKEN_TTL_MINUTES * 60,
    )


# ── V1: Fleet Score ─────────────────────────────────────────────────────────────────
@app.get("/v1/fleet/score", response_model=FleetScoreV1, tags=["v1"])
async def get_fleet_score_v1(
    client_id: str = Depends(get_current_client),
):
    """
    V1: Returns current Fleet Readiness Score and SLO compliance.
    JWT protected.
    """
    return FleetScoreV1(
        score=_latest["score"],
        environment=_latest["environment"],
        cluster=_latest["cluster"],
        slo_compliant=_latest["score"] >= 95.0,
        collected_at=_latest["collected_at"],
    )


# ── V2: Fleet Score (richer) ─────────────────────────────────────────────────────────
@app.get("/v2/fleet/score", response_model=FleetScoreV2, tags=["v2"])
async def get_fleet_score_v2(
    client_id: str = Depends(get_current_client),
):
    """
    V2: Returns Fleet Readiness Score with per-service breakdown
    and auto-generated remediation recommendations.
    JWT protected.
    """
    score = _latest["score"]
    degraded = _latest["degraded_services"]

    recommendations: list[str] = []
    if score < 95.0:
        recommendations.append("Check EKS node group health: kubectl get nodes")
    if score < 80.0:
        recommendations.append("Review ALB target group health in AWS Console")
        recommendations.append("Check ECS service desired vs running counts")
    if degraded:
        recommendations.append(
            f"Inspect degraded services: {', '.join(degraded[:3])}"
        )
    if not recommendations:
        recommendations.append("Fleet is healthy — no action required")

    breakdown = [
        ServiceBreakdown(
            name=b.get("name", "unknown"),
            health_ratio=b.get("health_ratio", 1.0),
            status="degraded" if b.get("health_ratio", 1.0) < 1.0 else "healthy",
        )
        for b in _latest["breakdown"]
    ]

    return FleetScoreV2(
        score=score,
        environment=_latest["environment"],
        cluster=_latest["cluster"],
        slo_compliant=score >= 95.0,
        collected_at=_latest["collected_at"],
        degraded_services=degraded,
        breach_reason=_latest["breach_reason"],
        service_breakdown=breakdown,
        recommendations=recommendations,
    )


# ── Score override (with idempotency) ─────────────────────────────────────────────
@app.post("/v1/fleet/score/override", tags=["v1"])
async def override_score(
    body: ScoreOverride,
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: str = Depends(get_current_client),
):
    """
    Override the fleet score for demo/testing (JWT protected).

    Supports X-Idempotency-Key header — same key within 60s returns
    the cached response without re-applying the override.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    idempotency_key = request.headers.get("X-Idempotency-Key")

    if idempotency_key:
        cached = get_cached(idempotency_key)
        if cached is not None:
            log.info("Idempotent override hit key=%s", idempotency_key)
            return cached

    _latest.update(
        score=body.score,
        environment=body.environment,
        cluster=body.cluster,
        degraded_services=[],
        breach_reason=f"Manual override: {body.reason}",
        breakdown=[],
        collected_at=int(time.time()),
    )
    record_score(body.score, body.environment, body.cluster, [], f"Override: {body.reason}")

    response = {
        "status": "overridden",
        "score": body.score,
        "reason": body.reason,
        "request_id": request_id,
    }

    if idempotency_key:
        set_cached(idempotency_key, response)

    background_tasks.add_task(
        deliver_score_event,
        {"score": body.score, "reason": body.reason, "environment": body.environment},
        request_id,
    )
    return response


# ── Score history with cursor pagination ───────────────────────────────────────────
@app.get("/v1/fleet/history", tags=["v1"])
async def fleet_history(
    cursor: Optional[str] = None,
    limit: int = 20,
    environment: Optional[str] = None,
    client_id: str = Depends(get_current_client),
):
    """
    Cursor-paginated Fleet Score history (JWT protected).

    Filter by environment with ?environment=prod.
    Use next_cursor from response to get the next page.
    limit is clamped 1–100.
    """
    return paginate_history(cursor=cursor, limit=limit, environment=environment)


# ── Webhook routes ──────────────────────────────────────────────────────────────────
@app.post(
    "/webhooks/register",
    response_model=WebhookRegistrationResponse,
    tags=["webhooks"],
)
async def register_webhook(
    body: WebhookRegistration,
    client_id: str = Depends(get_current_client),
):
    """
    Register a webhook URL (JWT protected).

    The service POSTs a fleet score event to your URL on each collection cycle
    when score drops below alert_threshold (default 80.0).
    Each delivery includes X-Webhook-Signature: sha256=<hmac> for verification.
    """
    url_str = str(body.url)
    newly_added = register_url(url_str)
    return WebhookRegistrationResponse(
        url=url_str,
        registered=newly_added,
        alert_threshold=body.alert_threshold,
        total_registered=len(list_urls()),
    )


@app.get("/webhooks", tags=["webhooks"])
async def get_webhooks(client_id: str = Depends(get_current_client)):
    """List registered webhook URLs (JWT protected)."""
    return {"webhooks": list_urls(), "total": len(list_urls())}
