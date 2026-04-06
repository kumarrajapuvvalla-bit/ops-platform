# OPA / Gatekeeper Policy: Require Labels
#
# Denies Pods that are missing required operational labels:
#   - app.kubernetes.io/name
#   - app.kubernetes.io/component
#   - environment
#
# These labels are required for:
#   - Prometheus metric filtering
#   - Cost attribution
#   - Incident investigation (kubectl get pods -l environment=prod)

package k8s.admission

import future.keywords.in

REQUIRED_LABELS := {
    "app.kubernetes.io/name",
    "app.kubernetes.io/component",
    "environment",
}

deny[msg] {
    input.request.kind.kind == "Pod"
    input.request.operation in {"CREATE", "UPDATE"}

    pod_labels := input.request.object.metadata.labels

    label := REQUIRED_LABELS[_]
    not pod_labels[label]

    msg := sprintf(
        "Pod '%v' is missing required label '%v'. "
        "All pods must have labels: %v",
        [
            input.request.object.metadata.name,
            label,
            concat(", ", REQUIRED_LABELS),
        ],
    )
}
