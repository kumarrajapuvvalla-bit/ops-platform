"""datadog_bridge.py — Forward P0 metrics to Datadog

Forwards fleet health metrics to Datadog when the readiness score
drops below the breach threshold (80). Falls back to structured
JSON stdout logging when no API key is configured.

Designed to be called by fleet_exporter.py when score < 80.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Score below this threshold triggers a P0 Datadog metric push
P0_THRESHOLD = 80.0


class DatadogBridge:
    """Forwards P0 fleet health breaches to Datadog.

    When DATADOG_API_KEY is not set, logs structured JSON to stdout
    instead (useful for local development and CI testing).
    """

    def __init__(self) -> None:
        self.api_key: Optional[str] = os.environ.get("DATADOG_API_KEY")
        self.app_key: Optional[str] = os.environ.get("DATADOG_APP_KEY")
        self.site: str = os.environ.get("DATADOG_SITE", "datadoghq.eu")
        self.enabled: bool = bool(self.api_key)

    def forward_p0_metric(
        self,
        metric_name: str,
        value: float,
        tags: list[str],
    ) -> bool:
        """Forward a P0 metric to Datadog if score is below threshold.

        Args:
            metric_name: Datadog metric name (e.g. 'fleet.readiness.score')
            value:        Current metric value
            tags:         List of Datadog tags (e.g. ['env:prod', 'cluster:eks'])

        Returns:
            True if the metric was successfully pushed, False otherwise.
        """
        # Only push if value indicates a P0 breach
        if value >= P0_THRESHOLD:
            return False

        if not self.enabled:
            self._log_to_stdout(metric_name, value, tags)
            return False

        try:
            return self._send_to_datadog(metric_name, value, tags)
        except Exception as exc:
            logger.error(
                "DatadogBridge failed to push metric",
                extra={"metric": metric_name, "error": str(exc)},
            )
            return False

    def _send_to_datadog(self, metric_name: str, value: float, tags: list[str]) -> bool:
        """Send the metric to Datadog via the API client.

        Imports datadog_api_client lazily so CI tests can run without
        the heavy datadog-api-client package installed.
        """
        try:
            from datadog_api_client import ApiClient, Configuration
            from datadog_api_client.v2.api.metrics_api import MetricsApi
            from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
            from datadog_api_client.v2.model.metric_payload import MetricPayload
            from datadog_api_client.v2.model.metric_point import MetricPoint
            from datadog_api_client.v2.model.metric_series import MetricSeries
        except ImportError:
            logger.warning("datadog-api-client not installed, falling back to stdout logging")
            self._log_to_stdout(metric_name, value, tags)
            return False

        configuration = Configuration()
        configuration.api_key["apiKeyAuth"] = self.api_key
        configuration.server_variables["site"] = self.site

        now = int(datetime.now(timezone.utc).timestamp())
        body = MetricPayload(
            series=[
                MetricSeries(
                    metric=metric_name,
                    type=MetricIntakeType.GAUGE,
                    points=[MetricPoint(timestamp=now, value=value)],
                    tags=tags,
                )
            ]
        )

        with ApiClient(configuration) as api_client:
            api = MetricsApi(api_client)
            api.submit_metrics(body=body)

        logger.info(
            "Datadog P0 metric pushed",
            extra={"metric": metric_name, "value": value, "tags": tags},
        )
        return True

    def _log_to_stdout(self, metric_name: str, value: float, tags: list[str]) -> None:
        """Emit a structured JSON log when Datadog is not configured."""
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "P0",
            "event": "fleet_breach",
            "metric": metric_name,
            "value": value,
            "tags": tags,
            "datadog_enabled": False,
        }
        print(json.dumps(payload), flush=True)
