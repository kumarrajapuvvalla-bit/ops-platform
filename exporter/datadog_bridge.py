"""datadog_bridge.py — Datadog Metrics Bridge

Forwards P0 threshold breaches from the Fleet Health Exporter to
Datadog as custom metrics and events. This bridge pattern allows
Prometheus to remain the primary metrics store while using Datadog
for alerting, dashboarding, and incident correlation.

Requires:
    DATADOG_API_KEY environment variable
    DATADOG_APP_KEY environment variable (for Events API)
"""

import logging
import os
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v2.api.metrics_api import MetricsApi
    from datadog_api_client.v2.model.metric_intake_type import MetricIntakeType
    from datadog_api_client.v2.model.metric_payload import MetricPayload
    from datadog_api_client.v2.model.metric_point import MetricPoint
    from datadog_api_client.v2.model.metric_series import MetricSeries
    DATADOG_AVAILABLE = True
except ImportError:
    DATADOG_AVAILABLE = False
    log.warning("datadog-api-client not installed — Datadog bridge disabled")


class DatadogBridge:
    """Pushes P0 metrics and events to Datadog."""

    def __init__(self) -> None:
        self.api_key = os.getenv("DATADOG_API_KEY", "")
        self.app_key = os.getenv("DATADOG_APP_KEY", "")
        self.enabled = bool(self.api_key) and DATADOG_AVAILABLE

        if not self.enabled:
            log.info("Datadog bridge disabled (no API key or package missing)")

    def push_p0_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[list[str]] = None,
    ) -> bool:
        """Submit a gauge metric to Datadog.

        Args:
            metric_name: Fully qualified metric name, e.g. ops_platform.fleet.readiness_score
            value: Current metric value
            tags: Optional list of tags e.g. ["env:prod", "cluster:ops-platform"]

        Returns:
            True if the metric was submitted successfully, False otherwise
        """
        if not self.enabled:
            log.debug("Datadog bridge disabled — skipping metric %s", metric_name)
            return False

        try:
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = self.api_key
            configuration.api_key["appKeyAuth"] = self.app_key

            with ApiClient(configuration) as api_client:
                api = MetricsApi(api_client)
                body = MetricPayload(
                    series=[
                        MetricSeries(
                            metric=metric_name,
                            type=MetricIntakeType.GAUGE,
                            points=[
                                MetricPoint(
                                    timestamp=int(time.time()),
                                    value=value,
                                )
                            ],
                            tags=tags or [],
                        )
                    ]
                )
                api.submit_metrics(body=body)
                log.info("Submitted Datadog metric %s=%.2f (tags=%s)", metric_name, value, tags)
                return True

        except Exception as exc:  # noqa: BLE001
            log.error("Failed to submit Datadog metric %s: %s", metric_name, exc)
            return False

    def is_healthy(self) -> bool:
        """Return True if the bridge is configured and available."""
        return self.enabled
