# OPA / Gatekeeper Policy: Deny Root Containers
#
# Denies any Pod that runs a container as root (uid 0) or
# does not set runAsNonRoot: true.
#
# Aligned with CIS Kubernetes Benchmark 5.2.6.

package k8s.admission

import future.keywords.in

deny[msg] {
    input.request.kind.kind == "Pod"
    input.request.operation in {"CREATE", "UPDATE"}

    container := input.request.object.spec.containers[_]
    _runs_as_root(container, input.request.object.spec)

    msg := sprintf(
        "Container '%v' in Pod '%v' must not run as root. "
        "Set securityContext.runAsNonRoot=true or securityContext.runAsUser > 0.",
        [container.name, input.request.object.metadata.name],
    )
}

# ── Helpers ───────────────────────────────────────────────────────────────

_runs_as_root(container, pod_spec) {
    # Explicit root uid at container level
    container.securityContext.runAsUser == 0
}

_runs_as_root(container, pod_spec) {
    # runAsNonRoot explicitly false at container level
    container.securityContext.runAsNonRoot == false
}

_runs_as_root(container, pod_spec) {
    # No container-level securityContext AND pod-level allows root
    not container.securityContext.runAsNonRoot
    not container.securityContext.runAsUser
    not pod_spec.securityContext.runAsNonRoot
    not pod_spec.securityContext.runAsUser
}
