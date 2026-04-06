# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the ops-platform project.
ADRs document significant technical decisions, the context in which they were made,
and the reasoning behind them.

## What is an ADR?

An Architecture Decision Record captures a single architectural decision:
- **Context** — what situation or forces drove the decision
- **Decision** — what was decided
- **Consequences** — what becomes easier or harder as a result

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](ADR-001-python-cdk-over-terraform.md) | Python CDK over Terraform/HCL for infrastructure | Accepted | 2026-03-01 |
| [ADR-002](ADR-002-distroless-operator-image.md) | Distroless base image for the Kubernetes operator | Accepted | 2026-03-05 |
| [ADR-003](ADR-003-controller-runtime-over-raw-client.md) | controller-runtime over raw Kubernetes client-go | Accepted | 2026-03-08 |

## ADR Lifecycle

`Proposed` → `Accepted` → `Deprecated` → `Superseded`

New decisions should be proposed as PRs with a new ADR file following the
naming convention `ADR-NNN-short-title.md`.
