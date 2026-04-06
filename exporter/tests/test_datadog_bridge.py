"""Unit tests for datadog_bridge.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, patch
from datadog_bridge import DatadogBridge


class TestDatadogBridge:
    def test_disabled_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("DATADOG_API_KEY", raising=False)
        monkeypatch.delenv("DATADOG_APP_KEY", raising=False)
        bridge = DatadogBridge()
        assert not bridge.is_healthy()

    def test_push_p0_metric_returns_false_when_disabled(self, monkeypatch):
        monkeypatch.delenv("DATADOG_API_KEY", raising=False)
        bridge = DatadogBridge()
        result = bridge.push_p0_metric("test.metric", 42.0)
        assert result is False

    def test_push_p0_metric_returns_true_when_enabled(self, monkeypatch):
        monkeypatch.setenv("DATADOG_API_KEY", "fake-api-key")
        monkeypatch.setenv("DATADOG_APP_KEY", "fake-app-key")

        with patch("datadog_bridge.DATADOG_AVAILABLE", True):
            with patch("datadog_bridge.ApiClient") as mock_client:
                mock_api = MagicMock()
                mock_client.return_value.__enter__ = MagicMock(return_value=mock_client)
                mock_client.return_value.__exit__ = MagicMock(return_value=False)

                with patch("datadog_bridge.MetricsApi", return_value=mock_api):
                    bridge = DatadogBridge()
                    result = bridge.push_p0_metric(
                        "ops_platform.fleet.score", 93.5, tags=["env:prod"]
                    )
                    assert result is True

    def test_push_handles_api_exception_gracefully(self, monkeypatch):
        monkeypatch.setenv("DATADOG_API_KEY", "fake-key")
        monkeypatch.setenv("DATADOG_APP_KEY", "fake-app")

        with patch("datadog_bridge.DATADOG_AVAILABLE", True):
            with patch("datadog_bridge.ApiClient", side_effect=Exception("network error")):
                bridge = DatadogBridge()
                result = bridge.push_p0_metric("test.metric", 1.0)
                assert result is False
