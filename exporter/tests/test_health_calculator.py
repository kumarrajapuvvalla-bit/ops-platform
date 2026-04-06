"""test_health_calculator.py — Unit tests for FleetReadinessCalculator

5 tests covering the spec requirements:
  1. Perfect health returns 100
  2. One degraded service lowers the score correctly
  3. All services down returns 0
  4. High latency alone triggers latency weight
  5. breach_reason is populated when score drops below 80

All tests are fully self-contained — no AWS calls, no boto3 imports.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from health_calculator import FleetReadinessCalculator, ReadinessResult, BREACH_SCORE_THRESHOLD

calc = FleetReadinessCalculator()


def healthy_service(
    latency_p99_ms: float = 100.0,
    error_rate: float = 0.0,
) -> dict:
    """Helper: build a fully healthy service metrics dict."""
    return {
        "healthy": True,
        "latency_p99_ms": latency_p99_ms,
        "error_rate": error_rate,
    }


class TestPerfectHealthReturns100:
    """Test 1: all services healthy, low latency, zero errors → score = 100."""

    def test_single_perfect_service(self):
        result = calc.calculate_score({
            "booking-svc": healthy_service(),
        })
        assert isinstance(result, ReadinessResult)
        assert result.score == 100.0
        assert result.degraded_services == []
        assert result.breach_reason is None

    def test_multiple_perfect_services(self):
        result = calc.calculate_score({
            "booking-svc": healthy_service(),
            "payment-svc": healthy_service(latency_p99_ms=50.0),
            "checkin-svc": healthy_service(latency_p99_ms=200.0, error_rate=0.01),
        })
        assert result.score == 100.0
        assert result.breach_reason is None


class TestOneDegradedServiceLowersScore:
    """Test 2: one unhealthy service in a fleet of 3 reduces the score."""

    def test_one_down_out_of_three_reduces_score(self):
        result = calc.calculate_score({
            "booking-svc": healthy_service(),
            "payment-svc": healthy_service(),
            "checkin-svc": {
                "healthy": False,
                "latency_p99_ms": 100.0,
                "error_rate": 0.0,
            },
        })
        assert result.score < 100.0
        assert "checkin-svc" in result.degraded_services
        assert len(result.degraded_services) == 1

    def test_degraded_service_name_appears_in_list(self):
        result = calc.calculate_score({
            "slow-svc": {
                "healthy": True,
                "latency_p99_ms": 800.0,
                "error_rate": 0.0,
            },
        })
        assert "slow-svc" in result.degraded_services


class TestAllServicesDownReturns0:
    """Test 3: every service unhealthy with max errors → score = 0."""

    def test_all_down_returns_zero(self):
        result = calc.calculate_score({
            "booking-svc": {"healthy": False, "latency_p99_ms": 9999.0, "error_rate": 1.0},
            "payment-svc": {"healthy": False, "latency_p99_ms": 9999.0, "error_rate": 1.0},
            "checkin-svc": {"healthy": False, "latency_p99_ms": 9999.0, "error_rate": 1.0},
        })
        assert result.score == 0.0
        assert len(result.degraded_services) == 3
        assert result.breach_reason is not None


class TestHighLatencyAloneTriggersLatencyWeight:
    """Test 4: service is healthy and error-free but latency exceeds SLO."""

    def test_high_latency_reduces_score(self):
        result = calc.calculate_score({
            "slow-svc": {
                "healthy": True,
                "latency_p99_ms": 1000.0,
                "error_rate": 0.0,
            },
        })
        assert result.score < 100.0
        assert result.score == pytest.approx(70.0, abs=1.0)
        assert "slow-svc" in result.degraded_services

    def test_latency_at_slo_boundary_is_not_degraded(self):
        result = calc.calculate_score({
            "boundary-svc": healthy_service(latency_p99_ms=500.0),
        })
        assert result.score == 100.0
        assert result.degraded_services == []


class TestBreachReasonPopulatedBelow80:
    """Test 5: breach_reason is a non-empty string when score < 80."""

    def test_breach_reason_set_when_score_below_80(self):
        result = calc.calculate_score({
            "critical-svc": {
                "healthy": False,
                "latency_p99_ms": 100.0,
                "error_rate": 0.0,
            },
        })
        assert result.score < BREACH_SCORE_THRESHOLD
        assert result.breach_reason is not None
        assert isinstance(result.breach_reason, str)
        assert len(result.breach_reason) > 0

    def test_breach_reason_none_when_score_above_80(self):
        result = calc.calculate_score({
            "healthy-svc": healthy_service(),
        })
        assert result.score >= BREACH_SCORE_THRESHOLD
        assert result.breach_reason is None

    def test_breach_reason_mentions_degraded_services(self):
        result = calc.calculate_score({
            "dead-svc": {"healthy": False, "latency_p99_ms": 100.0, "error_rate": 1.0},
        })
        assert result.breach_reason is not None
        assert "dead-svc" in result.breach_reason
