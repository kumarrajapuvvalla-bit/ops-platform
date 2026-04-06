"""health_calculator.py — Fleet Readiness Score Calculator

Computes a Fleet Readiness Score (0–100) from a dict of service health
metrics using a weighted scoring model:

    availability  50%  — is the service up?
    latency       30%  — is it responding within SLO?
    error_rate    20%  — are errors within acceptable threshold?

The ReadinessResult dataclass carries the score, a list of degraded
service names, and a human-readable breach_reason when score < 80.

Designed to be called by fleet_exporter.py every 30 seconds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Thresholds ────────────────────────────────────────────────────────────
LATENCY_SLO_MS = 500.0       # p99 latency SLO in milliseconds
ERROR_RATE_THRESHOLD = 0.05  # 5% error rate threshold
BREACH_SCORE_THRESHOLD = 80.0  # score below this triggers breach_reason

# ── Weights (must sum to 1.0) ───────────────────────────────────────────────
WEIGHTS = {
    "availability": 0.50,
    "latency": 0.30,
    "error_rate": 0.20,
}


@dataclass
class ReadinessResult:
    """Result of a single Fleet Readiness Score calculation.

    Attributes:
        score:             Fleet Readiness Score, 0.0–100.0
        degraded_services: Names of services that contributed negatively
        breach_reason:     Human-readable explanation when score < 80;
                           None when score >= 80
    """
    score: float
    degraded_services: list[str] = field(default_factory=list)
    breach_reason: Optional[str] = None


class FleetReadinessCalculator:
    """Calculates Fleet Readiness Score from a dict of service metrics.

    Expected input format for services:
        {
            "booking-service": {
                "healthy": True,           # bool — 50% weight
                "latency_p99_ms": 120.0,   # float — 30% weight
                "error_rate": 0.01,        # float 0–1 — 20% weight
            },
            "payment-service": { ... },
        }
    """

    def calculate_score(
        self,
        services: dict[str, dict],
    ) -> ReadinessResult:
        """Compute a Fleet Readiness Score from service health data.

        Args:
            services: Mapping of service name to health dict. Each dict
                      must contain keys: healthy (bool), latency_p99_ms
                      (float), error_rate (float 0–1).

        Returns:
            ReadinessResult with score, degraded_services, breach_reason
        """
        if not services:
            return ReadinessResult(
                score=0.0,
                degraded_services=[],
                breach_reason="No services registered",
            )

        service_scores: list[float] = []
        degraded: list[str] = []

        for name, metrics in services.items():
            svc_score = self._score_service(metrics)
            service_scores.append(svc_score)
            if svc_score < 100.0:
                degraded.append(name)

        # Fleet score = mean of individual service scores
        raw_score = sum(service_scores) / len(service_scores)
        final_score = round(max(0.0, min(100.0, raw_score)), 2)

        breach_reason: Optional[str] = None
        if final_score < BREACH_SCORE_THRESHOLD:
            causes = []
            if degraded:
                causes.append(f"{len(degraded)} service(s) degraded: {', '.join(degraded)}")
            breach_reason = "; ".join(causes) if causes else "Score below threshold"

        return ReadinessResult(
            score=final_score,
            degraded_services=degraded,
            breach_reason=breach_reason,
        )

    def _score_service(self, metrics: dict) -> float:
        """Score a single service 0–100 using the weighted model."""
        # ── Availability (50%) ─────────────────────────────────────────────────
        availability_score = 100.0 if metrics.get("healthy", False) else 0.0

        # ── Latency (30%) ─────────────────────────────────────────────────────
        latency = float(metrics.get("latency_p99_ms", 0.0))
        if latency <= 0:
            latency_score = 100.0
        elif latency <= LATENCY_SLO_MS:
            # Linear scale: 0ms = 100, 500ms = 100 (at SLO)
            latency_score = 100.0
        else:
            # Degrades linearly from 100 at SLO to 0 at 2x SLO
            overage = latency - LATENCY_SLO_MS
            latency_score = max(0.0, 100.0 - (overage / LATENCY_SLO_MS) * 100.0)

        # ── Error rate (20%) ───────────────────────────────────────────────────
        error_rate = float(metrics.get("error_rate", 0.0))
        if error_rate <= 0:
            error_score = 100.0
        elif error_rate <= ERROR_RATE_THRESHOLD:
            error_score = 100.0
        else:
            # Degrades: 5% error = 100, 100% error = 0
            overage = error_rate - ERROR_RATE_THRESHOLD
            error_score = max(0.0, 100.0 - (overage / (1.0 - ERROR_RATE_THRESHOLD)) * 100.0)

        # ── Weighted total ───────────────────────────────────────────────────────────
        return (
            WEIGHTS["availability"] * availability_score
            + WEIGHTS["latency"] * latency_score
            + WEIGHTS["error_rate"] * error_score
        )
