"""CDK assertions tests for the networking stack."""
import aws_cdk as cdk
from aws_cdk.assertions import Template
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from stacks.networking_stack import NetworkingStack


class TestNetworkingStack:
    def setup_method(self):
        self.app = cdk.App()
        self.stack = NetworkingStack(
            self.app, "TestNetworking", environment_name="dev",
            env=cdk.Environment(account="123456789012", region="eu-west-2")
        )
        self.template = Template.from_stack(self.stack)

    def test_vpc_is_created(self):
        self.template.has_resource("AWS::EC2::VPC", {})

    def test_flow_log_bucket_blocks_public_access(self):
        self.template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                }
            },
        )

    def test_flow_log_is_configured(self):
        self.template.resource_count_is("AWS::EC2::FlowLog", 1)
