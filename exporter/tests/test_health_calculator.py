"""Unit tests for health_calculator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from health_calculator import HealthCalculator, WEIGHTS, SLO_TARGETS


calc = HealthCalculator()


class TestComputeReadinessScore:
    def test_all_healthy_returns_100(self):
        score = calc.compute_readiness_score(
            eks_metrics={"ng-1": 1.0},
            ecs_metrics={"svc-a": 1.0},
            alb_metrics={"tg-1": 1.0},
            rds_metrics={"db-1": 0.0},  # 0 utilisation = perfect
        )
        assert score == 100.0

    def test_all_failed_returns_0(self):
        score = calc.compute_readiness_score(
            eks_metrics={"ng-1": 0.0},
            ecs_metrics={"svc-a": 0.0},
            alb_metrics={"tg-1": 0.0},
            rds_metrics={"db-1": 1.0},  # fully saturated
        )
        assert score == 0.0

    def test_empty_metrics_default_to_1(self):
        """No resources = no failures = max score."""
        score = calc.compute_readiness_score(
            eks_metrics={},
            ecs_metrics={},
            alb_metrics={},
            rds_metrics={},
        )
        assert score == 100.0

    def test_partial_ecs_failure_reduces_score(self):
        score = calc.compute_readiness_score(
            eks_metrics={"ng-1": 1.0},
            ecs_metrics={"svc-a": 0.5},  # half tasks running
            alb_metrics={"tg-1": 1.0},
            rds_metrics={"db-1": 0.0},
        )
        # 30% weight on ECS * 0.5 ratio = 0.15 deduction from ECS component
        assert score < 100.0
        assert score > 80.0

    def test_eks_failure_has_highest_impact(self):
        """EKS has highest weight (35%) so failure there hurts most."""
        score_eks_fail = calc.compute_readiness_score(
            eks_metrics={"ng-1": 0.0},
            ecs_metrics={"svc-a": 1.0},
            alb_metrics={"tg-1": 1.0},
            rds_metrics={"db-1": 0.0},
        )
        score_rds_fail = calc.compute_readiness_score(
            eks_metrics={"ng-1": 1.0},
            ecs_metrics={"svc-a": 1.0},
            alb_metrics={"tg-1": 1.0},
            rds_metrics={"db-1": 1.0},
        )
        assert score_eks_fail < score_rds_fail

    def test_score_is_bounded_0_to_100(self):
        for _ in range(10):
            score = calc.compute_readiness_score(
                eks_metrics={"ng": 0.7},
                ecs_metrics={"svc": 0.8},
                alb_metrics={"tg": 0.9},
                rds_metrics={"db": 0.3},
            )
            assert 0.0 <= score <= 100.0


class TestClassifySlo:
    def test_nominal_above_999(self):
        assert calc.classify_slo(99.95) == "nominal"

    def test_degraded_between_99_and_999(self):
        assert calc.classify_slo(99.5) == "degraded"

    def test_warning_between_95_and_99(self):
        assert calc.classify_slo(97.0) == "warning"

    def test_critical_below_95(self):
        assert calc.classify_slo(90.0) == "critical"

    def test_exactly_at_threshold(self):
        assert calc.classify_slo(99.9) == "nominal"
        assert calc.classify_slo(95.0) == "warning"
