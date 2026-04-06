#!/usr/bin/env python3
"""aws_ec2.py — Ansible Dynamic Inventory via boto3

Generates an Ansible-compatible dynamic inventory by querying the
AWS EC2 API for instances tagged with the project and environment.

Usage (as Ansible inventory source):
    ansible-playbook -i ansible/inventory/aws_ec2.py playbooks/eks_node_bootstrap.yml

Required env vars:
    AWS_REGION: AWS region to query (default: eu-west-2)
    ENVIRONMENT: Filter by this environment tag (default: all)
"""

import json
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import ClientError


def get_inventory() -> dict[str, Any]:
    region = os.getenv("AWS_REGION", "eu-west-2")
    environment = os.getenv("ENVIRONMENT", "")

    ec2 = boto3.client("ec2", region_name=region)

    filters = [{"Name": "tag:Project", "Values": ["ops-platform"]},
               {"Name": "instance-state-name", "Values": ["running"]}]

    if environment:
        filters.append({"Name": "tag:Environment", "Values": [environment]})

    try:
        response = ec2.describe_instances(Filters=filters)
    except ClientError as exc:
        print(f"Error querying EC2: {exc}", file=sys.stderr)
        sys.exit(1)

    inventory: dict[str, Any] = {
        "_meta": {"hostvars": {}},
        "all": {"children": ["eks_nodes", "ungrouped"]},
        "eks_nodes": {"hosts": [], "vars": {"ansible_user": "ec2-user", "ansible_ssh_private_key_file": "~/.ssh/ops-platform.pem"}},
    }

    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            ip = instance.get("PrivateIpAddress", "")
            if not ip:
                continue
            inventory["eks_nodes"]["hosts"].append(ip)
            tags = {t["Key"]: t["Value"] for t in instance.get("Tags", [])}
            inventory["_meta"]["hostvars"][ip] = {
                "instance_id": instance["InstanceId"],
                "instance_type": instance["InstanceType"],
                "availability_zone": instance["Placement"]["AvailabilityZone"],
                "environment": tags.get("Environment", "unknown"),
                "node_group": tags.get("aws:eks:cluster-name", "unknown"),
            }

    return inventory


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        print(json.dumps(get_inventory(), indent=2))
    elif len(sys.argv) == 2 and sys.argv[1] == "--host":
        print(json.dumps({}))
    else:
        print(json.dumps(get_inventory(), indent=2))
