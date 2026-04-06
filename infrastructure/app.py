"""app.py — AWS CDK Application Entry Point

Orchestrates all infrastructure stacks for the ops-platform.
All stacks are defined in infrastructure/stacks/ and composed here.

Usage:
    cdk synth          # Preview CloudFormation templates
    cdk deploy --all   # Deploy all stacks to AWS
    cdk diff           # Show pending changes

Stack dependency order:
    NetworkingStack -> EksStack -> FargateStack
    NetworkingStack -> DatabaseStack
    IamStack (standalone — no VPC dependency)
"""

import aws_cdk as cdk

from stacks.networking_stack import NetworkingStack
from stacks.eks_stack import EksStack
from stacks.fargate_stack import FargateStack
from stacks.database_stack import DatabaseStack
from stacks.iam_stack import IamStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "eu-west-2",
)

environment_name = app.node.try_get_context("environment") or "dev"

# Stack 1: Networking (foundation for all other stacks)
networking = NetworkingStack(
    app,
    f"OpsNetworking-{environment_name}",
    environment_name=environment_name,
    env=env,
)

# Stack 2: EKS cluster (depends on VPC from networking)
eks = EksStack(
    app,
    f"OpsEks-{environment_name}",
    vpc=networking.vpc,
    environment_name=environment_name,
    env=env,
)

# Stack 3: ECS/Fargate service for Fleet Health Exporter (depends on VPC)
fargate = FargateStack(
    app,
    f"OpsFargate-{environment_name}",
    vpc=networking.vpc,
    environment_name=environment_name,
    env=env,
)

# Stack 4: Aurora Serverless (depends on isolated subnets from networking)
database = DatabaseStack(
    app,
    f"OpsDatabase-{environment_name}",
    vpc=networking.vpc,
    environment_name=environment_name,
    env=env,
)

# Stack 5: IAM roles (standalone — referenced by other stacks via ARN)
iam = IamStack(
    app,
    f"OpsIam-{environment_name}",
    environment_name=environment_name,
    env=env,
)

cdk.Tags.of(app).add("Project", "ops-platform")
cdk.Tags.of(app).add("Environment", environment_name)
cdk.Tags.of(app).add("ManagedBy", "aws-cdk")
cdk.Tags.of(app).add("Owner", "platform-team")

app.synth()
