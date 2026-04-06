# OPA Kubernetes Admission Policies

This directory contains Open Policy Agent (OPA) Rego policies for Kubernetes
admission control. They are designed to be deployed via
[OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/)
as `ConstraintTemplate` + `Constraint` resources.

## Why Policy-as-Code?

The root cause of **INC-001** (node memory pressure cascade) was a pod deployed
without resource limits. These policies prevent that class of incident at
admission time — the pod would be rejected before it ever starts.

## Policies

| Policy | File | Purpose | CIS Ref |
|--------|------|---------|----------|
| Require Resource Limits | `require-resource-limits.rego` | Blocks pods without CPU + memory limits | CIS 5.2.4 |
| Deny Root Containers | `deny-root-containers.rego` | Blocks containers running as uid 0 | CIS 5.2.6 |
| Require Labels | `require-labels.rego` | Enforces operational label standards | Internal |

## Local Testing

```bash
# Install OPA CLI
brew install opa  # macOS
# or: https://www.openpolicyagent.org/docs/latest/#1-download-opa

# Test a policy against a sample input
opa eval \
  -d policies/k8s/require-resource-limits.rego \
  -i policies/tests/pod-missing-limits.json \
  'data.k8s.admission.deny'

# Run all policy tests
opa test policies/ -v
```

## Deploying to EKS via Gatekeeper

```bash
# Install Gatekeeper
kubectl apply -f https://raw.githubusercontent.com/open-policy-agent/gatekeeper/v3.16.3/deploy/gatekeeper.yaml

# Apply ConstraintTemplate (wraps the Rego policy as a CRD)
kubectl apply -f policies/gatekeeper/require-resource-limits-template.yaml

# Apply Constraint (activates the policy for specific namespaces)
kubectl apply -f policies/gatekeeper/require-resource-limits-constraint.yaml
```

## Connection to INC-001

`require-resource-limits.rego` directly implements action item #2 from
[INC-001](../postmortems/INC-001-node-pressure-cascade.md):

> Deploy OPA/Gatekeeper policy to reject pods without resource limits

The policy error message even links back to the postmortem, closing the loop
between incident response and preventive enforcement.
