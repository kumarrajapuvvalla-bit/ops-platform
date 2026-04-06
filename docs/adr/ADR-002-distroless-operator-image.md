# ADR-002: Distroless Base Image for the Kubernetes Operator

**Status:** Accepted
**Date:** 2026-03-05
**Author:** Kumar Raja Puvvalla
**Reviewers:** Platform Team

---

## Context

The Self-Healing Operator is a Go binary deployed to production EKS clusters.
The operator image needs a base layer for the final Docker stage. Candidates
considered:

1. **`golang:1.22-alpine`** — small Alpine Linux image with shell and package manager
2. **`ubuntu:22.04`** — full Ubuntu with apt, coreutils, bash
3. **`gcr.io/distroless/static:nonroot`** — Google's distroless image: no shell,
   no package manager, no libc (for statically linked binaries), runs as uid 65532

Security context:
- The operator runs in production with cluster-wide RBAC permissions to read and
  patch Deployments
- Any container escape or RCE vulnerability in the operator would have broad blast
  radius
- The operator is a compiled Go binary that has no runtime dependencies beyond
  the Linux kernel

## Decision

We will use **`gcr.io/distroless/static:nonroot`** as the final runtime image.

The Dockerfile uses a two-stage build:
1. `golang:1.22` builder stage — compiles a statically linked binary
   (`CGO_ENABLED=0 GOOS=linux`)
2. `gcr.io/distroless/static:nonroot` runtime stage — copies only the binary

## Rationale

### Attack Surface Reduction

| Image | Shell | Package Manager | libc | CVEs (typical) | Size |
|-------|-------|-----------------|------|----------------|------|
| ubuntu:22.04 | bash | apt | glibc | 20–50+ | ~80MB |
| alpine:3.19 | sh | apk | musl | 5–15 | ~8MB |
| distroless/static:nonroot | ❌ none | ❌ none | ❌ none | 0–2 | ~2MB |

With no shell, an attacker who achieves RCE in the container cannot run arbitrary
shell commands. With no package manager, they cannot install tools. The attack
path from container compromise to full cluster compromise is significantly longer.

### Non-root by default

Distroless `nonroot` runs as uid 65532 without a `USER` directive needed. This
is automatically compliant with Kubernetes `runAsNonRoot: true` pod security
standards.

### Binary compatibility

Go binaries compiled with `CGO_ENABLED=0` are fully statically linked — they
embedded all dependencies and do not need libc, libpthread, or any shared
libraries at runtime. The `distroless/static` image is specifically designed
for this pattern.

### Acknowledged Trade-offs

| Trade-off | Impact | Mitigation |
|-----------|--------|------------|
| No shell for debugging | Cannot `kubectl exec` and run `ls` | Use `kubectl debug` with ephemeral containers |
| No tools inside container | No `curl`, `wget` for health checks | Go binary handles its own `/healthz` probe |
| Distroless requires static binary | Fails if CGO is used | Set `CGO_ENABLED=0` in build command |

## Consequences

**Positive:**
- Near-zero CVE count on the final image
- Smallest possible image size (~2MB runtime vs ~80MB ubuntu)
- Non-root execution by default without explicit `USER` directive
- Passes all common container security scanners (Trivy, Grype) cleanly

**Negative:**
- Debugging requires `kubectl debug` with a sidecar, not `kubectl exec`
- Build complexity slightly higher (mandatory two-stage Dockerfile)
- Team members unfamiliar with distroless may be confused initially

## Related

- `operator/Dockerfile` — two-stage build implementation
- `operator/main.go` — CGO-free Go code
- [ADR-001](ADR-001-python-cdk-over-terraform.md)
- [ADR-003](ADR-003-controller-runtime-over-raw-client.md)
