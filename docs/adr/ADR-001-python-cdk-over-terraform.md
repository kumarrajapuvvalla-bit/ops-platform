# ADR-001: Python CDK over Terraform/HCL for Infrastructure

**Status:** Accepted
**Date:** 2026-03-01
**Author:** Kumar Raja Puvvalla
**Reviewers:** Platform Team

---

## Context

The ops-platform needs a robust Infrastructure as Code (IaC) solution to provision
AWS resources including EKS, ECS/Fargate, VPC, ALB, and Aurora Serverless. The two
primary candidates considered were:

1. **Terraform (HCL)** — the dominant IaC tool in the market, with a large ecosystem
   and widespread adoption
2. **AWS CDK in Python** — AWS's first-party IaC framework using real programming languages

The engineering context for this decision:

- The platform team is predominantly Python-proficient
- The project already uses Python for the Fleet Health Exporter and data tooling
- We need complex conditional logic in our stack definitions (e.g., prod vs dev sizing)
- We want to use proper unit testing (pytest) for infrastructure assertions
- The team values avoiding context-switching between HCL syntax and Python

## Decision

We will use **AWS CDK with Python** (`aws-cdk-lib`) as the primary IaC tool.

All infrastructure stacks will be in `infrastructure/stacks/` as Python classes
inheriting from `cdk.Stack`. Tests will use the `aws_cdk.assertions` library
with pytest.

## Rationale

### Why CDK over Terraform

**Real programming language constructs:**
In Terraform HCL, expressing "use t3.large in prod, t3.medium in dev" requires
terraform `locals` and conditional expressions. In Python CDK this is just:
```python
instance_type = "t3.large" if environment_name == "prod" else "t3.medium"
```

**Testable infrastructure:**
CDK stacks can be unit tested with `aws_cdk.assertions.Template`. HCL has
`terraform test` but it is newer and less mature. We can run our infrastructure
tests in CI with no AWS credentials required (`cdk synth` runs locally):
```python
def test_vpc_has_3_azs():
    template = Template.from_stack(NetworkingStack(...))
    template.has_resource("AWS::EC2::VPC", ...)
```

**Reusable constructs:**
CDK allows us to create L3 constructs (higher-level abstractions) using standard
Python class inheritance. We can package common patterns (e.g., "an EKS cluster
with IRSA and autoscaler") as a reusable library.

**Python ecosystem:**
CDK stacks can import `boto3` to query live AWS state during synth, enabling
dynamic configuration that is impossible in static HCL.

### Why not Terraform

- HCL requires learning a bespoke language; Python CDK leverages existing skills
- Terraform's `count` / `for_each` patterns for dynamic resources are less readable
  than Python list comprehensions
- Mixing Python application code and HCL IaC creates a context-switching cost

### Acknowledged Trade-offs

| Trade-off | Impact | Mitigation |
|-----------|--------|------------|
| CDK is AWS-only | Cannot port to Azure/GCP without rewrite | Azure CDK exists; scope is AWS-only |
| Smaller ecosystem than Terraform | Fewer community modules | AWS provides official L2/L3 constructs |
| CDK abstracts CloudFormation | Debugging requires reading CFN templates | `cdk synth` makes this transparent |
| Team Terraform knowledge devalued | Some re-learning needed | Core IaC concepts transfer directly |

## Consequences

**Positive:**
- Infrastructure code is testable with pytest, same framework as application code
- Complex conditional logic (prod vs dev sizing) is natural Python
- CI can run `cdk synth` + `pytest` without AWS credentials
- Developers already familiar with Python can contribute to infra

**Negative:**
- Engineers expecting Terraform will need to learn CDK patterns
- CDK version upgrades can introduce breaking changes
- CDK generates verbose CloudFormation which can be harder to debug

## Related

- `infrastructure/stacks/` — all CDK stack implementations
- `infrastructure/tests/` — CDK assertion tests
- [ADR-002](ADR-002-distroless-operator-image.md) — operator container image decision
