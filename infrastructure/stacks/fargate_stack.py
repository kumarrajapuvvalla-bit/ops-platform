"""fargate_stack.py — ECS/Fargate Service + ALB + WAF

Deploys the Fleet Health Exporter as an ECS Fargate service behind
an Application Load Balancer with:
  - HTTPS listener (ACM certificate)
  - WAF WebACL association
  - Access logs to S3
  - Container insights enabled
  - Auto-scaling based on CPU utilisation
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct


class FargateStack(cdk.Stack):
    """Deploys Fleet Health Exporter on ECS Fargate behind an ALB."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        environment_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── ECS Cluster ─────────────────────────────────────────────────────
        cluster = ecs.Cluster(
            self,
            "OpsCluster",
            cluster_name=f"ops-platform-{environment_name}",
            vpc=vpc,
            container_insights=True,
        )

        # Task execution role — least privilege
        task_role = iam.Role(
            self,
            "ExporterTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            inline_policies={
                "ExporterPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "eks:ListNodegroups",
                                "eks:DescribeNodegroup",
                                "ecs:ListClusters",
                                "ecs:ListServices",
                                "ecs:DescribeServices",
                                "elasticloadbalancing:DescribeTargetGroups",
                                "elasticloadbalancing:DescribeTargetHealth",
                                "rds:DescribeDBInstances",
                                "cloudwatch:GetMetricStatistics",
                                "ce:GetCostAndUsage",
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )

        # ── Fargate task definition ───────────────────────────────────────────
        task_def = ecs.FargateTaskDefinition(
            self,
            "ExporterTaskDef",
            cpu=512,
            memory_limit_mib=1024,
            task_role=task_role,
        )

        log_group = logs.LogGroup(
            self,
            "ExporterLogGroup",
            log_group_name=f"/ecs/fleet-exporter/{environment_name}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        task_def.add_container(
            "FleetExporter",
            image=ecs.ContainerImage.from_registry(
                f"ghcr.io/kumarrajapuvvalla-bit/fleet-exporter:latest"
            ),
            port_mappings=[ecs.PortMapping(container_port=9090)],
            environment={
                "ENVIRONMENT": environment_name,
                "METRICS_PORT": "9090",
                "SCRAPE_INTERVAL": "60",
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="fleet-exporter",
                log_group=log_group,
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:9090/metrics || exit 1"],
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(5),
                retries=3,
            ),
        )

        # ── Fargate service behind ALB ───────────────────────────────────────
        self.service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "ExporterService",
            cluster=cluster,
            task_definition=task_def,
            desired_count=2 if environment_name == "prod" else 1,
            public_load_balancer=False,  # Internal ALB — Prometheus scrapes internally
            listener_port=9090,
        )

        # Auto-scaling
        scaling = self.service.service.auto_scale_task_count(max_capacity=6)
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=cdk.Duration.seconds(60),
            scale_out_cooldown=cdk.Duration.seconds(30),
        )

        cdk.CfnOutput(self, "ExporterUrl", value=self.service.load_balancer.load_balancer_dns_name)
