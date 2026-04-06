# OPA / Gatekeeper Policy: Require Resource Limits
#
# Denies any Pod (or workload creating Pods) that has a container
# without explicit CPU and memory limits.
#
# Directly addresses the root cause of INC-001 (noisy neighbour OOM).
# Deploy via Gatekeeper ConstraintTemplate + Constraint.
#
# Test locally:
#   opa eval -d require-resource-limits.rego \
#     -i test/pod-no-limits.json \
#     'data.k8s.admission.deny'

package k8s.admission

import future.keywords.in

# ── Deny rule ──────────────────────────────────────────────────────────

deny[msg] {
    # Only evaluate Pod create/update operations
    input.request.kind.kind == "Pod"
    input.request.operation in {"CREATE", "UPDATE"}

    container := input.request.object.spec.containers[_]
    not _has_resource_limits(container)

    msg := sprintf(
        "Container '%v' in Pod '%v' must specify resources.limits.cpu and resources.limits.memory. "
        "Missing limits caused INC-001 (node memory pressure cascade). "
        "See: https://github.com/kumarrajapuvvalla-bit/ops-platform/blob/main/postmortems/INC-001-node-pressure-cascade.md",
        [container.name, input.request.object.metadata.name],
    )
}

deny[msg] {
    input.request.kind.kind == "Pod"
    input.request.operation in {"CREATE", "UPDATE"}

    container := input.request.object.spec.initContainers[_]
    not _has_resource_limits(container)

    msg := sprintf(
        "Init container '%v' in Pod '%v' must specify resources.limits.cpu and resources.limits.memory.",
        [container.name, input.request.object.metadata.name],
    )
}

# ── Helper ────────────────────────────────────────────────────────────────

_has_resource_limits(container) {
    container.resources.limits.cpu
    container.resources.limits.memory
}
