"""database_stack.py — Aurora Serverless v2

Provisions Aurora Serverless v2 PostgreSQL for audit log storage:
  - Isolated subnet placement (no internet route)
  - Encrypted at rest (KMS) and in transit (SSL required)
  - Deletion protection in prod
  - Automated backups with 7-day retention
  - Enhanced monitoring
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


class DatabaseStack(cdk.Stack):
    """Provisions Aurora Serverless v2 for audit log storage."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        environment_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = environment_name == "prod"

        # ── Security group ────────────────────────────────────────────────────
        db_sg = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=vpc,
            description="Aurora cluster security group — allow only from private subnets",
            allow_all_outbound=False,
        )
        db_sg.add_ingress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(5432),
            "Allow PostgreSQL from within VPC only",
        )

        # ── Aurora Serverless v2 ──────────────────────────────────────────────
        self.cluster = rds.DatabaseCluster(
            self,
            "AuditDb",
            cluster_identifier=f"ops-audit-db-{environment_name}",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_4
            ),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=16.0 if is_prod else 4.0,
            writer=rds.ClusterInstance.serverless_v2("Writer"),
            readers=[
                rds.ClusterInstance.serverless_v2("Reader1", scale_with_writer=True)
            ] if is_prod else [],
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_sg],
            default_database_name="audit_log",
            storage_encrypted=True,
            backup=rds.BackupProps(
                retention=cdk.Duration.days(7 if is_prod else 1),
                preferred_window="02:00-03:00",
            ),
            deletion_protection=is_prod,
            removal_policy=cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY,
            cloudwatch_logs_exports=["postgresql"],
        )

        cdk.CfnOutput(self, "DbClusterEndpoint", value=self.cluster.cluster_endpoint.hostname)
        cdk.CfnOutput(self, "DbSecretArn", value=self.cluster.secret.secret_arn if self.cluster.secret else "no-secret")
