# ops-platform

> Self-Healing Cloud Operations Platform — themed around a 24/7 global flight booking backbone.

[![Python Exporter](https://github.com/kumarrajapuvvalla-bit/ops-platform/actions/workflows/exporter-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/ops-platform/actions/workflows/exporter-ci.yml)
[![Go Operator](https://github.com/kumarrajapuvvalla-bit/ops-platform/actions/workflows/operator-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/ops-platform/actions/workflows/operator-ci.yml)
[![CDK Synth](https://github.com/kumarrajapuvvalla-bit/ops-platform/actions/workflows/cdk-ci.yml/badge.svg)](https://github.com/kumarrajapuvvalla-bit/ops-platform/actions/workflows/cdk-ci.yml)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        ops-platform                             │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────┐ │
│  │    Python    │   │      Go      │   │   GitLab CI/CD      │ │
│  │   Exporter   │   │   Operator   │   │   10-Stage Pipeline │ │
│  └──────────────┘   └──────────────┘   └─────────────────────┘ │
│         │                   │                    │              │
│  Fleet Health         Self-Healing          Deploy to EKS      │
│  Exporter             Operator              via Helm           │
│  (Prometheus)         (controller-runtime)                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           AWS Infrastructure (Python CDK)                │  │
│  │   EKS  │  ECS/Fargate  │  VPC  │  ALB  │  Aurora RDS    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                  Observability Stack                     │  │
│  │  Prometheus  │  Grafana  │  Datadog  │  Alert Manager    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
ops-platform/
├── exporter/               # Python — Fleet Health Exporter
│   ├── fleet_exporter.py   # Core boto3 + prometheus_client logic
│   ├── health_calculator.py# Fleet Readiness Score algorithm
│   ├── datadog_bridge.py   # Forwards P0 metrics to Datadog
│   ├── tests/
│   └── Dockerfile
├── operator/               # Go — Self-Healing Kubernetes Operator
│   ├── main.go
│   ├── controllers/
│   ├── api/v1/
│   └── config/
├── infrastructure/         # Python AWS CDK
│   ├── app.py
│   └── stacks/
├── helm/                   # Helm charts for both services
├── ansible/                # EKS node bootstrap + hardening
├── .gitlab-ci.yml          # 10-stage GitLab pipeline
├── observability/          # Prometheus rules, Grafana dashboards, Datadog monitors
├── runbooks/               # Incident response runbooks
└── postmortems/            # Realistic incident postmortems
```

## Components

| Component | Language | Purpose |
|-----------|----------|---------|
| Fleet Health Exporter | Python | Custom Prometheus exporter — polls EKS, ECS, ALB, RDS via boto3 and calculates Fleet Readiness Score |
| Self-Healing Operator | Go | Kubernetes controller-runtime operator — watches `FlightRoute` CRD and auto-heals replica drift |
| AWS Infrastructure | Python CDK | All AWS infra as code — VPC, EKS, ECS/Fargate, ALB, Aurora RDS, IAM |
| CI/CD Pipeline | GitLab YAML + Ansible | 10-stage pipeline + EKS node bootstrap and security hardening playbooks |

## Key Design Decisions

- **Python CDK over Terraform/HCL** — demonstrates the same IaC skill (state management, modular stacks) in Python, which is explicitly listed in target job specs alongside CDK usage at scale.
- **controller-runtime Operator** — Go is the language of the Kubernetes ecosystem. A custom CRD/operator signals deeper platform engineering knowledge than Helm alone.
- **Aviation domain** — Fleet Readiness Score mirrors the dispatch reliability metric used by airlines. It gives every metric and SLO a concrete, memorable business context.
- **Datadog + Prometheus dual-stack** — reflects real production environments where both tools coexist. The bridge pattern demonstrates integration thinking.

## Quick Start

```bash
# Run the Fleet Health Exporter locally
cd exporter
pip install -r requirements.txt
AWS_REGION=eu-west-2 python fleet_exporter.py
# Metrics available at http://localhost:9090/metrics

# Run the operator locally (requires a kubeconfig)
cd operator
go run main.go

# Synth CDK stacks
cd infrastructure
pip install -r requirements.txt
cdk synth
```

## Observability

See `observability/` for:
- Prometheus alert rules (SLO breach, operator health, node pressure)
- Grafana dashboard JSON (fleet operations, cost burn)
- Datadog monitor JSON (P0 pod crashloop, high ALB latency)

## Runbooks

See `runbooks/` for structured incident response procedures:
- EKS node failure
- Failed deployment rollback
- High latency incident
- Operator reconcile stall
