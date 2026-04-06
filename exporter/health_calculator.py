"""health_calculator.py — Fleet Readiness Score Algorithm

Calculates a Fleet Readiness Score (0–100) per environment, modelled on
the Dispatch Reliability Rate used in commercial aviation:

    Dispatch Reliability = (departures without technical delay / total departures) * 100

Our equivalent:
    Fleet Readiness Score = weighted average of all resource health ratios

Weights reflect operational criticality:
    EKS nodes:    35% — cluster compute is the foundation
    ECS services: 30% — application availability
    ALB targets:  25% — traffic routing health
    RDS:          10% — database connections (usually more stable)
"""

from typing import Optional

# Criticality weights — must sum to 1.0
WEIGHTS = {
    "eks": 0.35,
    "ecs": 0.30,
    "alb": 0.25,
    "rds": 0.10,
}

# SLO thresholds
SLO_TARGETS = {
    "critical": 99.9,   # P0 page immediately
    "high": 99.0,       # P1 alert
    "medium": 95.0,     # warning
}


class HealthCalculator:
    """Computes the Fleet Readiness Score from component health metrics."""

    def compute_readiness_score(
        self,
        eks_metrics: dict[str, float],
        ecs_metrics: dict[str, float],
        alb_metrics: dict[str, float],
        rds_metrics: dict[str, float],
    ) -> float:
        """Return a Fleet Readiness Score between 0 and 100.

        Args:
            eks_metrics: Map of node group name -> healthy ratio (0-1)
            ecs_metrics: Map of service name -> running/desired ratio (0-1)
            alb_metrics: Map of target group name -> healthy ratio (0-1)
            rds_metrics: Map of db identifier -> connection utilisation (0-1, lower is better)

        Returns:
            Fleet Readiness Score 0–100
        """
        component_scores = {
            "eks": self._average_ratio(eks_metrics),
            "ecs": self._average_ratio(ecs_metrics),
            "alb": self._average_ratio(alb_metrics),
            "rds": self._rds_score(rds_metrics),
        }

        weighted_sum = sum(
            WEIGHTS[component] * score
            for component, score in component_scores.items()
        )

        return round(weighted_sum * 100, 2)

    def classify_slo(self, score: float) -> str:
        """Classify a readiness score against SLO thresholds."""
        if score >= SLO_TARGETS["critical"]:
            return "nominal"
        elif score >= SLO_TARGETS["high"]:
            return "degraded"
        elif score >= SLO_TARGETS["medium"]:
            return "warning"
        else:
            return "critical"

    @staticmethod
    def _average_ratio(metrics: dict[str, float]) -> float:
        """Return mean ratio, defaulting to 1.0 if no metrics (no resources = no failures)."""
        if not metrics:
            return 1.0
        return sum(metrics.values()) / len(metrics)

    @staticmethod
    def _rds_score(rds_metrics: dict[str, float]) -> float:
        """For RDS, high utilisation is bad. Invert the metric.

        connection_utilisation 0.0 = fully available = score 1.0
        connection_utilisation 1.0 = fully saturated = score 0.0
        """
        if not rds_metrics:
            return 1.0
        avg_utilisation = sum(rds_metrics.values()) / len(rds_metrics)
        return max(0.0, 1.0 - avg_utilisation)
