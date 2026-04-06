# ops-platform — Architecture Deep Dive

This document covers the detailed architecture of each component, data flows,
and key design decisions. For the rationale behind specific choices, see
[`docs/adr/`](adr/README.md).

---

## Component Architecture

### 1. Fleet Health Exporter (Python)

**Data flow:**

```
Every 30 seconds:

  boto3 API calls (parallel)
  ├─ eks.list_nodegroups + describe_nodegroup  ─┬─► EKS health ratio
  ├─ ecs.list_services + describe_services    ─┤
  ├─ elbv2.describe_target_health             ─┤─► FleetReadinessCalculator
  └─ cloudwatch.get_metric_statistics (RDS)   ─┘        │
                                                         ▼
                                               ReadinessResult
                                               ├─ score: float (0-100)
                                               ├─ degraded_services: list
                                               └─ breach_reason: str | None
                                                         │
                          ┌─────────────────────────▼
                          │                       score < 80?
                          ▼                            │ YES
                 Prometheus Gauges                     ▼
                 (port 8000/metrics)           DatadogBridge.push_p0_metric()
                 - fleet_readiness_score               │
                 - eks_node_health_ratio               ▼
                 - ecs_service_running_ratio   Datadog custom metric
                 - alb_target_healthy_ratio    + PagerDuty alert
                 - rds_connection_utilisation
```

**Scoring algorithm (weighted):**

```
For each service:
  service_score = (0.50 × availability_score)
                + (0.30 × latency_score)
                + (0.20 × error_rate_score)

Fleet score = mean(all service scores) × 100

Thresholds:
  score ≥ 99.9  → nominal
  score ≥ 99.0  → degraded (P1 alert)
  score ≥ 95.0  → warning
  score < 80.0  → critical (P0 alert + Datadog push)
```

---

### 2. Self-Healing Operator (Go) — State Machine

```
                    kubectl apply FlightRoute CR
                              │
                              ▼
                    ┌──────────────┐
                    │  RECONCILING  │
                    └──────────────┘
                              │
              ┌─────────────────────┤
              │                     │
              ▼                     ▼
  Deployment not found       Deployment found
              │                     │
              ▼               ┌──────────────────┐
  Requeue 30s            │  replicas >= minReplicas?  │
                         └──────────────────┘
                              │           │
                             YES           NO
                              │           │
                              ▼           ▼
                     Update status    healingEnabled?
                     SloCompliant=T       │       │
                     Requeue 30s         YES      NO
                                          │       │
                                          ▼       ▼
                                   Scale to    Log drift,
                                   minReplicas  observe only
                                       │        Requeue 30s
                                       ▼
                              Emit K8s Event
                              (AutoHealed)
                                       │
                                       ▼
                              Update Status:
                              - currentReplicas
                              - lastHealedAt
                              - healCount++
                              - SloCompliant=F
                                       │
                                       ▼
                              Requeue 30s
```

**Reconciliation performance:**
- Average reconcile loop: < 100ms (in-cluster)
- Cache hit rate: ~99% (controller-runtime informer cache)
- Leader election: lease-based, 15s renewal, 40s timeout

---

### 3. CDK Stack Dependency Graph

```
 IamStack                NetworkingStack
    │                         │
    │                ┌───────────────────│
    │                │          VPC          │
    │                │   (public/private/     │
    │                │    isolated subnets)    │
    │                └───────────────────┘
    │                     │          │          │
    │                     ▼          ▼          ▼
    │               EksStack    FargateStack  DatabaseStack
    │               EKS 1.29    ECS/Fargate   Aurora
    │               +OIDC       +ALB          Serverless v2
    │               +NodeGroup  +CloudWatch   +Encryption
    │               +Autoscaler +HealthCheck  +Isolated subnet
    │
    └──► All roles consumed by EksStack (IRSA) + FargateStack (task role)
```

**State management:**
- Remote state: S3 + DynamoDB (per-environment, encrypted)
- Stack outputs are cross-referenced via `CfnOutput` — no hardcoded ARNs
- CDK context values (`--context environment=prod`) control prod vs dev sizing

---

### 4. GitLab CI/CD Pipeline Flow

```
PR created
    │
    ▼
 [lint] ─────────────────────────────────────────────────
  flake8 (Python) + golangci-lint (Go) + helm lint
    │ pass
    ▼
 [unit-test] ───────────────────────────────────────
  pytest (exporter) + go test (operator) + pytest (CDK)
    │ pass
    ▼
 [cdk-synth] ───────────────────────────────────────
  cdk synth (no AWS credentials needed)
    │ pass
    ▼
 [security-scan] ─────────────────────────────────
  trivy fs + bandit + Checkov (CDK output)
    │ pass
    ▼
 [docker-build] ──────────────────────────────────
  build fleet-exporter + operator images
  trivy image scan (CRITICAL/HIGH block)
  push to ECR via OIDC (no static keys)
    │ pass (main branch only)
    ▼
 [helm-package] + [deploy-dev] ─────────────────
  helm upgrade --install to dev namespace
    │
    ▼
 [integration-test] ────────────────────────────
  curl /metrics → assert HTTP 200
    │ pass
    ▼
 [deploy-prod] ──────────────────────────────────
  when: manual (human approval gate)
  only: v* tags
    │
    ▼
 [notify] ───────────────────────────────────────
  Slack webhook on success/failure
```

---

## Security Architecture

### Defence in Depth

```
Layer 1: Supply chain
  ├─ Dependabot auto-updates (weekly)
  ├─ Trivy image scanning (CI gate)
  ├─ SBOM generation on release (Syft)
  └─ Gitleaks secret scanning

Layer 2: Build time
  ├─ Bandit static analysis (Python)
  ├─ gosec security scanner (Go)
  ├─ Checkov IaC scan (CDK output)
  └─ CodeQL (TypeScript/YAML)

Layer 3: Admission control (OPA/Gatekeeper)
  ├─ require-resource-limits.rego
  ├─ deny-root-containers.rego
  └─ require-labels.rego

Layer 4: Runtime
  ├─ Distroless operator image (no shell)
  ├─ Non-root containers (uid 1000)
  ├─ ReadOnlyRootFilesystem
  └─ IRSA (no long-lived credentials)

Layer 5: Infrastructure
  ├─ EKS private API endpoint
  ├─ Aurora in isolated subnets
  ├─ VPC Flow Logs to S3
  └─ Least-privilege IAM (no wildcards)
```

---

## Estimated Monthly AWS Cost (eu-west-2)

> Estimates based on on-demand pricing. Reserved instances would reduce
> EKS node costs by ~40%. Costs assume moderate traffic.

| Resource | Spec | Est. Monthly (GBP) |
|----------|------|--------------------|
| EKS cluster (control plane) | 1 cluster | ~£72 |
| EKS nodes (2x t3.medium) | On-demand, 24/7 | ~£55 |
| NAT Gateway (single AZ) | ~50GB data | ~£38 |
| Aurora Serverless v2 | 0.5–2 ACU | ~£25 |
| ALB | ~100 LCU-hours | ~£18 |
| ECR storage | 2 images | ~£2 |
| CloudWatch logs | ~10GB/month | ~£5 |
| S3 (state + flow logs) | ~5GB | ~£1 |
| **Total (dev)** | | **~£216/month** |
| **Total (prod, HA)** | 3 nodes, multi-AZ NAT | **~£380/month** |

> **Cost optimisation:** Switch EKS nodes to Spot instances for dev (−60%),
> enable S3 Intelligent-Tiering for flow logs (−30% storage cost),
> use Aurora auto-pause for dev (scales to 0 ACU when idle).
