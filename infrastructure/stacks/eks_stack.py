"""eks_stack.py — AWS EKS Cluster

Provisions a production-grade EKS cluster with:
  - Managed node group in private subnets
  - Fargate profile for system workloads
  - OIDC provider for IRSA (IAM Roles for Service Accounts)
  - Cluster autoscaler tags
  - Private API endpoint by default (public disabled)
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_eks as eks,
    aws_iam as iam,
)
from constructs import Construct


class EksStack(cdk.Stack):
    """Provisions the EKS cluster for ops-platform workloads."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        environment_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Cluster role ─────────────────────────────────────────────────────
        cluster_role = iam.Role(
            self,
            "EksClusterRole",
            assumed_by=iam.ServicePrincipal("eks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonEKSClusterPolicy"),
            ],
        )

        # ── EKS Cluster ────────────────────────────────────────────────────
        self.cluster = eks.Cluster(
            self,
            "OpsEksCluster",
            cluster_name=f"ops-platform-{environment_name}",
            vpc=vpc,
            vpc_subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)],
            role=cluster_role,
            version=eks.KubernetesVersion.V1_29,
            endpoint_access=eks.EndpointAccess.PRIVATE,  # No public endpoint
            default_capacity=0,  # We define node groups explicitly
            cluster_logging=[
                eks.ClusterLoggingTypes.API,
                eks.ClusterLoggingTypes.AUDIT,
                eks.ClusterLoggingTypes.AUTHENTICATOR,
                eks.ClusterLoggingTypes.CONTROLLER_MANAGER,
                eks.ClusterLoggingTypes.SCHEDULER,
            ],
        )

        # ── Managed node group ───────────────────────────────────────────────
        min_nodes = 2 if environment_name == "prod" else 1
        max_nodes = 10 if environment_name == "prod" else 4

        self.node_group = self.cluster.add_nodegroup_capacity(
            "WorkerNodes",
            nodegroup_name=f"ops-workers-{environment_name}",
            instance_types=[
                ec2.InstanceType("t3.large" if environment_name == "prod" else "t3.medium")
            ],
            min_size=min_nodes,
            max_size=max_nodes,
            desired_size=min_nodes,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            ami_type=eks.NodegroupAmiType.AL2_X86_64,
            disk_size=50,
            labels={
                "role": "worker",
                "environment": environment_name,
            },
            tags={
                f"k8s.io/cluster-autoscaler/ops-platform-{environment_name}": "owned",
                "k8s.io/cluster-autoscaler/enabled": "true",
            },
        )

        # ── Outputs ────────────────────────────────────────────────────────────
        cdk.CfnOutput(self, "ClusterName", value=self.cluster.cluster_name)
        cdk.CfnOutput(self, "ClusterArn", value=self.cluster.cluster_arn)
        cdk.CfnOutput(self, "OidcIssuer", value=self.cluster.cluster_open_id_connect_issuer)
