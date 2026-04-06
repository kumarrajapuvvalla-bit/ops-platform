"""networking_stack.py — VPC, Subnets, NAT Gateways

Builds a production-grade multi-AZ VPC with:
  - Public subnets (ALB, NAT gateway EIPs)
  - Private subnets (EKS nodes, ECS tasks)
  - Isolated subnets (RDS Aurora — no internet route)
  - One NAT gateway per AZ for HA
  - VPC Flow Logs to S3 for audit trail
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_logs as logs,
    aws_s3 as s3,
)
from constructs import Construct


class NetworkingStack(cdk.Stack):
    """Provisions the VPC and subnet layout for ops-platform."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = environment_name

        # ── VPC ───────────────────────────────────────────────────────────────
        self.vpc = ec2.Vpc(
            self,
            "OpsVpc",
            vpc_name=f"ops-platform-{environment_name}",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=3,
            nat_gateways=3,  # One per AZ for HA
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=28,
                ),
            ],
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # ── VPC Flow Logs ──────────────────────────────────────────────────
        flow_log_bucket = s3.Bucket(
            self,
            "FlowLogBucket",
            bucket_name=f"ops-platform-flow-logs-{environment_name}-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="delete-old-logs",
                    expiration=cdk.Duration.days(90),
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                            transition_after=cdk.Duration.days(30),
                        )
                    ],
                )
            ],
        )

        self.vpc.add_flow_log(
            "VpcFlowLog",
            destination=ec2.FlowLogDestination.to_s3(flow_log_bucket),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

        # ── Outputs ────────────────────────────────────────────────────────────
        cdk.CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        cdk.CfnOutput(
            self,
            "PrivateSubnetIds",
            value=",".join([s.subnet_id for s in self.vpc.private_subnets]),
        )
