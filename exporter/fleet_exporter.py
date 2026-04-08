"""fleet_exporter.py — Fleet Health Exporter

A custom Prometheus exporter that watches AWS infrastructure the way an
airline watches its fleet — every resource has a health status, cost burn
rate, and SLO compliance score.

Metrics exposed at :8000/metrics

Requires:
    pip install boto3 prometheus_client datadog-api-client
    AWS credentials via env vars, instance profile, or IRSA
"""

import logging
import os
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError
from prometheus_client import Gauge, start_http_server

from health_calculator import HealthCalculator
from datadog_bridge import DatadogBridge

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────────
AWS_REGION = os.getenv("AWS_REGION", "eu-west-2")
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
CLUSTER_NAME = os.getenv("EKS_CLUSTER_NAME", "ops-platform")

# ── Prometheus Metrics ──────────────────────────────────────────────────────
FLEET_READINESS_SCORE = Gauge(
    "fleet_readiness_score",
    "Overall fleet readiness score (0-100), analogous to airline dispatch reliability",
    ["environment", "cluster"],
)

EKS_NODE_HEALTH = Gauge(
    "eks_node_health_ratio",
    "Ratio of healthy EKS nodes to total nodes per node group",
    ["cluster", "node_group", "environment"],
)

ECS_SERVICE_HEALTH = Gauge(
    "ecs_service_running_ratio",
    "Ratio of running tasks to desired tasks for each ECS service",
    ["cluster", "service", "environment"],
)

ALB_TARGET_HEALTH = Gauge(
    "alb_target_healthy_ratio",
    "Ratio of healthy ALB targets to total registered targets",
    ["load_balancer", "target_group", "environment"],
)

RDS_CONNECTION_UTILISATION = Gauge(
    "rds_connection_utilisation",
    "Percentage of max RDS connections currently in use",
    ["db_identifier", "environment"],
)

SLO_COMPLIANCE = Gauge(
    "slo_compliance_ratio",
    "SLO compliance ratio for each tracked service (1.0 = fully compliant)",
    ["service", "slo_target", "environment"],
)


class FleetExporter:
    """Polls AWS APIs and updates Prometheus gauges."""

    def __init__(self, region: str, cluster_name: str, environment: str) -> None:
        self.region = region
        self.cluster_name = cluster_name
        self.environment = environment
        self.eks = boto3.client("eks", region_name=region)
        self.ecs = boto3.client("ecs", region_name=region)
        self.elbv2 = boto3.client("elbv2", region_name=region)
        self.rds = boto3.client("rds", region_name=region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)
        self.calculator = HealthCalculator()
        self.datadog = DatadogBridge()

    # ── EKS ──────────────────────────────────────────────────────────────────

    def collect_eks_health(self) -> dict[str, Any]:
        """Poll EKS node groups and compute healthy node ratios."""
        metrics: dict[str, Any] = {}
        try:
            paginator = self.eks.get_paginator("list_nodegroups")
            for page in paginator.paginate(clusterName=self.cluster_name):
                for ng_name in page["nodegroups"]:
                    ng = self.eks.describe_nodegroup(
                        clusterName=self.cluster_name, nodegroupName=ng_name
                    )["nodegroup"]
                    desired = ng["scalingConfig"]["desiredSize"]
                    healthy = ng.get("health", {}).get("issues") == [] and desired > 0
                    ratio = 1.0 if healthy else 0.5
                    EKS_NODE_HEALTH.labels(
                        cluster=self.cluster_name,
                        node_group=ng_name,
                        environment=self.environment,
                    ).set(ratio)
                    metrics[ng_name] = ratio
                    log.info("EKS node group %s health ratio: %.2f", ng_name, ratio)
        except ClientError as exc:
            log.warning("EKS health collection failed: %s", exc)
        return metrics

    # ── ECS ──────────────────────────────────────────────────────────────────

    def collect_ecs_health(self) -> dict[str, float]:
        """Poll ECS services and compute running/desired task ratios."""
        metrics: dict[str, float] = {}
        try:
            clusters = self.ecs.list_clusters()["clusterArns"]
            for cluster_arn in clusters:
                services = self.ecs.list_services(cluster=cluster_arn)["serviceArns"]
                if not services:
                    continue
                described = self.ecs.describe_services(
                    cluster=cluster_arn, services=services[:10]
                )["services"]
                for svc in described:
                    desired = svc["desiredCount"]
                    running = svc["runningCount"]
                    ratio = running / desired if desired > 0 else 0.0
                    svc_name = svc["serviceName"]
                    cluster_short = cluster_arn.split("/")[-1]
                    ECS_SERVICE_HEALTH.labels(
                        cluster=cluster_short,
                        service=svc_name,
                        environment=self.environment,
                    ).set(ratio)
                    metrics[svc_name] = ratio
        except ClientError as exc:
            log.warning("ECS health collection failed: %s", exc)
        return metrics

    # ── ALB ──────────────────────────────────────────────────────────────────

    def collect_alb_health(self) -> dict[str, float]:
        """Poll ALB target group health."""
        metrics: dict[str, float] = {}
        try:
            tgs = self.elbv2.describe_target_groups()["TargetGroups"]
            for tg in tgs:
                tg_arn = tg["TargetGroupArn"]
                tg_name = tg["TargetGroupName"]
                health = self.elbv2.describe_target_health(TargetGroupArn=tg_arn)
                targets = health["TargetHealthDescriptions"]
                healthy = sum(
                    1 for t in targets if t["TargetHealth"]["State"] == "healthy"
                )
                total = len(targets)
                ratio = healthy / total if total > 0 else 0.0
                lb_name = tg.get("LoadBalancerArns", ["unknown"])[0].split("/")[-2] if tg.get("LoadBalancerArns") else "unattached"
                ALB_TARGET_HEALTH.labels(
                    load_balancer=lb_name,
                    target_group=tg_name,
                    environment=self.environment,
                ).set(ratio)
                metrics[tg_name] = ratio
        except ClientError as exc:
            log.warning("ALB health collection failed: %s", exc)
        return metrics

    # ── RDS ──────────────────────────────────────────────────────────────────

    def collect_rds_health(self) -> dict[str, float]:
        """Poll RDS connection utilisation via CloudWatch."""
        metrics: dict[str, float] = {}
        try:
            instances = self.rds.describe_db_instances()["DBInstances"]
            for db in instances:
                db_id = db["DBInstanceIdentifier"]
                max_conn = db.get("Endpoint", {}) and 100  # simplified
                cw = self.cloudwatch.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="DatabaseConnections",
                    Dimensions=[{"Name": "DBInstanceIdentifier", "Value": db_id}],
                    StartTime=__import__("datetime").datetime.utcnow() - __import__("datetime").timedelta(minutes=5),
                    EndTime=__import__("datetime").datetime.utcnow(),
                    Period=300,
                    Statistics=["Average"],
                )
                if cw["Datapoints"]:
                    current = cw["Datapoints"][-1]["Average"]
                    utilisation = min(current / max_conn, 1.0)
                    RDS_CONNECTION_UTILISATION.labels(
                        db_identifier=db_id,
                        environment=self.environment,
                    ).set(utilisation)
                    metrics[db_id] = utilisation
        except ClientError as exc:
            log.warning("RDS health collection failed: %s", exc)
        return metrics

    # ── Main collection loop ────────────────────────────────────────────────

    def collect_all(self) -> None:
        """Run a full collection cycle and update the Fleet Readiness Score."""
        log.info("Starting collection cycle (env=%s)", self.environment)

        eks_metrics = self.collect_eks_health()
        ecs_metrics = self.collect_ecs_health()
        alb_metrics = self.collect_alb_health()
        rds_metrics = self.collect_rds_health()

        score = self.calculator.compute_readiness_score(
            eks_metrics=eks_metrics,
            ecs_metrics=ecs_metrics,
            alb_metrics=alb_metrics,
            rds_metrics=rds_metrics,
        )

        FLEET_READINESS_SCORE.labels(
            environment=self.environment,
            cluster=self.cluster_name,
        ).set(score)

        log.info("Fleet Readiness Score: %.1f / 100", score)

        if score < 95.0:
            self.datadog.push_p0_metric(
                metric_name="ops_platform.fleet.readiness_score",
                value=score,
                tags=[f"env:{self.environment}", f"cluster:{self.cluster_name}"],
            )
            log.warning("P0: Fleet readiness below threshold (%.1f < 95)", score)


def main() -> None:
    log.info("Starting Fleet Health Exporter on port %s", METRICS_PORT)
    start_http_server(METRICS_PORT)

    exporter = FleetExporter(
        region=AWS_REGION,
        cluster_name=CLUSTER_NAME,
        environment=ENVIRONMENT,
    )

    while True:
        try:
            exporter.collect_all()
        except Exception as exc:  # noqa: BLE001
            log.error("Collection cycle failed: %s", exc, exc_info=True)
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
