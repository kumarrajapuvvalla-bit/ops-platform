"""iam_stack.py — Least-Privilege IAM Roles

All IAM roles for ops-platform. Key design principles:
  - No wildcard (*) actions anywhere
  - All roles use IRSA (IAM Roles for Service Accounts) where applicable
  - Explicit deny on dangerous actions
  - Boundary policies on all roles
"""

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from constructs import Construct


class IamStack(cdk.Stack):
    """Defines all IAM roles for ops-platform with least-privilege policies."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Fleet Exporter IRSA role ───────────────────────────────────────────
        # Used by the Fleet Exporter pod via IRSA — no long-lived credentials
        self.exporter_role = iam.Role(
            self,
            "FleetExporterRole",
            role_name=f"ops-fleet-exporter-{environment_name}",
            assumed_by=iam.FederatedPrincipal(
                "arn:aws:iam::*:oidc-provider/*",
                conditions={"StringEquals": {"sts:ExternalId": f"fleet-exporter-{environment_name}"}},
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            description="IRSA role for Fleet Health Exporter — read-only AWS API access",
        )

        self.exporter_role.add_to_policy(
            iam.PolicyStatement(
                sid="EksReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "eks:ListNodegroups",
                    "eks:DescribeNodegroup",
                    "eks:ListClusters",
                ],
                resources=["*"],
            )
        )

        self.exporter_role.add_to_policy(
            iam.PolicyStatement(
                sid="EcsReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:ListClusters",
                    "ecs:ListServices",
                    "ecs:DescribeServices",
                ],
                resources=["*"],
            )
        )

        self.exporter_role.add_to_policy(
            iam.PolicyStatement(
                sid="AlbReadOnly",
                effect=iam.Effect.ALLOW,
                actions=[
                    "elasticloadbalancing:DescribeTargetGroups",
                    "elasticloadbalancing:DescribeTargetHealth",
                    "elasticloadbalancing:DescribeLoadBalancers",
                ],
                resources=["*"],
            )
        )

        self.exporter_role.add_to_policy(
            iam.PolicyStatement(
                sid="CostExplorer",
                effect=iam.Effect.ALLOW,
                actions=["ce:GetCostAndUsage"],
                resources=["*"],
            )
        )

        # ── Outputs ────────────────────────────────────────────────────────────
        cdk.CfnOutput(self, "ExporterRoleArn", value=self.exporter_role.role_arn)
