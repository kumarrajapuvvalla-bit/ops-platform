# CHANGELOG

All notable changes to ops-platform are documented here.
This project follows [Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- OPA/Gatekeeper policy-as-code for Kubernetes admission control
- SBOM generation workflow using Syft
- Automated release pipeline with version tagging
- Formal SLO definitions as code
- Architecture Decision Records (ADRs) for key technical choices
- Local docker-compose stack for zero-credential demo
- Grafana datasource and dashboard auto-provisioning
- Dependabot configuration for automated dependency updates

---

## [1.1.0] — 2026-04-06

### Added
- `operator/Dockerfile`: multi-stage distroless build (`golang:1.22` + `gcr.io/distroless/static:nonroot`)
- `ansible/playbooks/observability_agent.yml`: Datadog agent + Prometheus node_exporter install
- `helm/ops-platform/templates/`: complete Helm template set (deployment, HPA, PDB, service)
- `observability/prometheus/alerts/eks_node_pressure.yml`: NodeMemoryPressure, NodeDiskPressure, PodCrashLooping alerts
- `runbooks/high_latency_incident.md`: P1 response procedure with Datadog runbook link format
- `postmortems/INC-001-node-pressure-cascade.md`: full UTC timeline postmortem

### Fixed
- `exporter/health_calculator.py`: rewritten with `ReadinessResult` dataclass and service-dict scoring (weights: availability 50%, latency 30%, error_rate 20%)
- `exporter/Dockerfile`: corrected to port 8000 and `python:3.11-slim` base
- `exporter/tests/test_health_calculator.py`: 5 spec-compliant named test classes
- `operator/go.mod`: pinned `controller-runtime` to `v0.17.0`
- `observability/prometheus/alerts/fleet_slo.yml`: added `OperatorHealingLoop` alert
- `observability/grafana/dashboards/fleet_operations.json`: 4 panels with datasource variable and 30s refresh
- `README.md`: removed all references to external company names

---

## [1.0.0] — 2026-04-05

### Added
- Initial release of ops-platform
- **Component 1**: Python Fleet Health Exporter with boto3/Prometheus integration
- **Component 2**: Go Self-Healing Kubernetes Operator with `FlightRoute` CRD
- **Component 3**: AWS CDK infrastructure (VPC, EKS, ECS/Fargate, Aurora, IAM)
- **Component 4**: GitLab CI/CD 10-stage pipeline
- **Ansible**: EKS node bootstrap + CIS Level 1 hardening playbooks
- **Helm**: ops-platform chart with HPA, PDB, ServiceMonitor
- **Observability**: Prometheus alert rules, Grafana dashboards, Datadog monitors
- **Runbooks**: eks_node_failure, failed_deployment_rollback, operator_reconcile_stall
- **Postmortems**: fleet_exporter_p0_2026_03_15

[Unreleased]: https://github.com/kumarrajapuvvalla-bit/ops-platform/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/kumarrajapuvvalla-bit/ops-platform/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/kumarrajapuvvalla-bit/ops-platform/releases/tag/v1.0.0
