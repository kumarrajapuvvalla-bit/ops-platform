"""api_webhooks.py — Outbound webhook registry for fleet score events.

On each collection cycle the fleet exporter calls deliver_score_event()
which fans out to all registered URLs with:
  - HMAC-SHA256 signature (X-Webhook-Signature)
  - Correlation ID (X-Request-ID)
  - 3 attempts with 2s/4s/8s exponential backoff

In production:
  - Persist registrations to DynamoDB
  - Use SQS + Lambda for reliable async delivery
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any

import httpx
from pydantic import BaseModel, HttpUrl

log = logging.getLogger(__name__)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret-ops-platform")
_REGISTRY: list[str] = []


class WebhookRegistration(BaseModel):
    url: HttpUrl
    description: str = ""
    alert_threshold: float = 80.0  # only fire when score drops below this


class WebhookRegistrationResponse(BaseModel):
    url: str
    registered: bool
    alert_threshold: float
    total_registered: int


def register_url(url: str) -> bool:
    if url not in _REGISTRY:
        _REGISTRY.append(url)
        return True
    return False


def list_urls() -> list[str]:
    return list(_REGISTRY)


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def deliver_score_event(payload: dict[str, Any], request_id: str) -> None:
    """Fan-out fleet score event to all registered webhooks."""
    if not _REGISTRY:
        return

    async def _send(url: str) -> None:
        body = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": request_id,
            "X-Webhook-Signature": f"sha256={_sign(body)}",
            "X-Event-Type": "fleet.score",
            "X-Delivered-At": str(int(time.time())),
        }
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, content=body, headers=headers)
                    if resp.status_code < 500:
                        log.info("Webhook delivered url=%s status=%d attempt=%d", url, resp.status_code, attempt)
                        return
                    log.warning("Webhook 5xx url=%s status=%d attempt=%d", url, resp.status_code, attempt)
            except Exception as exc:
                log.warning("Webhook error url=%s attempt=%d: %s", url, attempt, exc)
            await asyncio.sleep(2 ** attempt)
        log.error("Webhook permanently failed url=%s request_id=%s", url, request_id)

    await asyncio.gather(*[_send(u) for u in _REGISTRY], return_exceptions=True)
