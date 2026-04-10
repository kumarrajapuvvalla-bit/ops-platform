import pytest
from fastapi.testclient import TestClient
from api_server import app, update_latest_score

client = TestClient(app)


def _token(client_id="grafana-agent", secret="grafana-secret") -> str:
    r = client.post("/token", json={"client_id": client_id, "client_secret": secret})
    assert r.status_code == 200
    return r.json()["access_token"]


def _seed_score(score=92.5):
    update_latest_score(
        score=score,
        environment="dev",
        cluster="ops-platform",
        degraded_services=["booking-svc"] if score < 95 else [],
        breach_reason="test breach" if score < 80 else None,
        breakdown=[{"name": "booking-svc", "health_ratio": 0.8}],
    )


# ── Auth ───────────────────────────────────────────────────────────────────
class TestAuth:
    def test_valid_credentials_return_token(self):
        r = client.post("/token", json={"client_id": "grafana-agent", "client_secret": "grafana-secret"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_invalid_secret_rejected(self):
        r = client.post("/token", json={"client_id": "grafana-agent", "client_secret": "wrong"})
        assert r.status_code == 401

    def test_unknown_client_rejected(self):
        r = client.post("/token", json={"client_id": "hacker", "client_secret": "any"})
        assert r.status_code == 401

    def test_protected_route_requires_token(self):
        r = client.get("/v1/fleet/score")
        assert r.status_code == 403

    def test_invalid_token_rejected(self):
        r = client.get("/v1/fleet/score", headers={"Authorization": "Bearer fake"})
        assert r.status_code == 401

    def test_valid_token_accepted(self):
        _seed_score()
        token = _token()
        r = client.get("/v1/fleet/score", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200


# ── Versioning ────────────────────────────────────────────────────────────────
class TestVersioning:
    def test_v1_returns_score_only(self):
        _seed_score(92.5)
        token = _token()
        r = client.get("/v1/fleet/score", headers={"Authorization": f"Bearer {token}"})
        body = r.json()
        assert r.status_code == 200
        assert "score" in body
        assert "degraded_services" not in body  # v1 doesn't expose breakdown

    def test_v2_returns_breakdown_and_recommendations(self):
        _seed_score(70.0)
        token = _token()
        r = client.get("/v2/fleet/score", headers={"Authorization": f"Bearer {token}"})
        body = r.json()
        assert r.status_code == 200
        assert "service_breakdown" in body
        assert "recommendations" in body
        assert len(body["recommendations"]) >= 1

    def test_v2_slo_compliant_when_score_above_95(self):
        _seed_score(98.0)
        token = _token()
        r = client.get("/v2/fleet/score", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["slo_compliant"] is True

    def test_v1_slo_non_compliant_when_score_below_95(self):
        _seed_score(80.0)
        token = _token()
        r = client.get("/v1/fleet/score", headers={"Authorization": f"Bearer {token}"})
        assert r.json()["slo_compliant"] is False


# ── Idempotency ────────────────────────────────────────────────────────────────
class TestIdempotency:
    def test_same_key_returns_identical_response(self):
        import uuid
        token = _token()
        key = str(uuid.uuid4())
        headers = {"Authorization": f"Bearer {token}", "X-Idempotency-Key": key}
        body = {"score": 75.0, "reason": "load test", "environment": "dev", "cluster": "ops-platform"}
        r1 = client.post("/v1/fleet/score/override", json=body, headers=headers)
        r2 = client.post("/v1/fleet/score/override", json=body, headers=headers)
        assert r1.json()["request_id"] == r2.json()["request_id"]

    def test_different_keys_produce_different_request_ids(self):
        import uuid
        token = _token()
        body = {"score": 85.0, "reason": "test", "environment": "dev", "cluster": "ops-platform"}
        r1 = client.post("/v1/fleet/score/override", json=body,
                         headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())})
        r2 = client.post("/v1/fleet/score/override", json=body,
                         headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())})
        assert r1.json()["request_id"] != r2.json()["request_id"]


# ── Pagination ────────────────────────────────────────────────────────────────
class TestPagination:
    def test_history_returns_paginated_items(self):
        for i in range(5):
            _seed_score(90.0 + i)
        token = _token()
        r = client.get("/v1/fleet/history?limit=3", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert "has_more" in body
        assert len(body["items"]) <= 3

    def test_cursor_advances_page(self):
        for i in range(10):
            _seed_score(85.0 + i)
        token = _token()
        r1 = client.get("/v1/fleet/history?limit=3", headers={"Authorization": f"Bearer {token}"})
        cursor = r1.json().get("next_cursor")
        if cursor:
            r2 = client.get(f"/v1/fleet/history?limit=3&cursor={cursor}",
                            headers={"Authorization": f"Bearer {token}"})
            assert r2.status_code == 200

    def test_history_requires_auth(self):
        r = client.get("/v1/fleet/history")
        assert r.status_code == 403


# ── Webhooks ────────────────────────────────────────────────────────────────
class TestWebhooks:
    def test_register_webhook(self):
        import uuid
        token = _token()
        url = f"https://hooks.example.com/{uuid.uuid4()}"
        r = client.post("/webhooks/register",
                        json={"url": url, "description": "grafana alert"},
                        headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["registered"] is True

    def test_duplicate_url_not_re_registered(self):
        import uuid
        token = _token()
        url = f"https://hooks.example.com/{uuid.uuid4()}"
        client.post("/webhooks/register", json={"url": url},
                    headers={"Authorization": f"Bearer {token}"})
        r2 = client.post("/webhooks/register", json={"url": url},
                         headers={"Authorization": f"Bearer {token}"})
        assert r2.json()["registered"] is False

    def test_list_webhooks_requires_auth(self):
        r = client.get("/webhooks")
        assert r.status_code == 403

    def test_list_webhooks_returns_array(self):
        token = _token()
        r = client.get("/webhooks", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert "webhooks" in r.json()
