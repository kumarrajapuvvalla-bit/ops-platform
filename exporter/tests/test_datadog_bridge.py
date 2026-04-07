"""test_datadog_bridge.py — Unit tests for DatadogBridge"""

import sys
import os
import logging
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datadog_bridge import DatadogBridge


class TestDatadogBridge:
    """Tests for DatadogBridge.forward_p0_metric()"""

    def test_disabled_when_no_api_key(self, caplog):
        """Bridge should log to stdout when DATADOG_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATADOG_API_KEY", None)
            bridge = DatadogBridge()
            with caplog.at_level(logging.INFO):
                result = bridge.forward_p0_metric(
                    "fleet.readiness.breach", 61.0, ["env:prod"]
                )
        assert result is False

    def test_push_p0_metric_returns_false_when_disabled(self):
        """When DATADOG_API_KEY is absent, forward_p0_metric returns False."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATADOG_API_KEY", None)
            bridge = DatadogBridge()
            result = bridge.forward_p0_metric("test.metric", 42.0, [])
        assert result is False

    def test_push_p0_metric_skips_when_score_above_threshold(self):
        """forward_p0_metric should not push when score >= 80 (not a P0)."""
        with patch.dict(os.environ, {"DATADOG_API_KEY": "fake-key"}, clear=False):
            bridge = DatadogBridge()
            with patch.object(bridge, "_send_to_datadog", return_value=True) as mock_send:
                result = bridge.forward_p0_metric("fleet.score", 85.0, ["env:prod"])
        assert result is False
        mock_send.assert_not_called()

    def test_push_p0_metric_calls_send_when_score_below_threshold(self):
        """forward_p0_metric should call _send_to_datadog when score < 80."""
        with patch.dict(os.environ, {"DATADOG_API_KEY": "fake-key"}, clear=False):
            bridge = DatadogBridge()
            with patch.object(bridge, "_send_to_datadog", return_value=True) as mock_send:
                result = bridge.forward_p0_metric("fleet.score", 61.0, ["env:prod"])
        mock_send.assert_called_once()

    def test_push_handles_exception_gracefully(self):
        """forward_p0_metric should return False and not raise on exceptions."""
        with patch.dict(os.environ, {"DATADOG_API_KEY": "fake-key"}, clear=False):
            bridge = DatadogBridge()
            with patch.object(bridge, "_send_to_datadog", side_effect=Exception("network error")):
                result = bridge.forward_p0_metric("fleet.score", 61.0, ["env:prod"])
        assert result is False
