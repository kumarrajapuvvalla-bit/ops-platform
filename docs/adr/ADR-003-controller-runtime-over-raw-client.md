# ADR-003: controller-runtime over Raw Kubernetes client-go

**Status:** Accepted
**Date:** 2026-03-08
**Author:** Kumar Raja Puvvalla
**Reviewers:** Platform Team

---

## Context

The Self-Healing Operator needs to watch Kubernetes resources (Deployments,
FlightRoute CRDs) and react to state changes. Two approaches were considered
for building the controller:

1. **Raw `client-go`** — the official Kubernetes Go client library. Provides
   Informers, WorkQueues, and Listers at a low level of abstraction.
2. **`sigs.k8s.io/controller-runtime`** — a higher-level framework used internally
   by Kubebuilder and Operator SDK. Wraps client-go with opinionated abstractions.

Engineering context:
- The team has intermediate Go experience but limited Kubernetes controller internals knowledge
- The operator needs: CRD support, leader election, health probes, metrics, graceful shutdown
- Time to production is a constraint
- Long-term maintainability matters

## Decision

We will use **`sigs.k8s.io/controller-runtime v0.17.0`** as the controller
framework.

The operator is structured as a standard controller-runtime `Reconciler` with
a `Manager` that handles leader election, health probes, and metrics exposure
out of the box.

## Rationale

### controller-runtime provides all required features for free

To build the same operator with raw client-go we would need to implement:

| Feature | client-go approach | controller-runtime |
|---------|-------------------|--------------------|
| Watch + cache | Set up Informer + ListWatch manually | `ctrl.NewControllerManagedBy(...).For(...)` |
| Work queue | Implement rate-limiting WorkQueue | Built-in, automatic |
| Leader election | Configure lease-based election manually | `ctrl.Options{LeaderElection: true}` |
| Health/ready probes | Write HTTP server manually | `mgr.AddHealthzCheck(...)` |
| Metrics | Wire `prometheus/client_go` manually | Built-in on `:8080/metrics` |
| Graceful shutdown | Handle SIGTERM manually | `ctrl.SetupSignalHandler()` |
| Status subresource | Manual patch logic | `r.Status().Update(ctx, obj)` |

With controller-runtime, all of this is provided. Our code focuses entirely on
business logic (detect drift, heal deployment, emit event).

### The Reconcile pattern matches our use case exactly

controller-runtime's `Reconcile(ctx, req)` pattern is a perfect fit:
1. Fetch the `FlightRoute` CR
2. Fetch the backing `Deployment`
3. Compare current vs desired state
4. If drift detected, heal and requeue
5. Return `ctrl.Result{RequeueAfter: 30s}`

This is idiomatic controller-runtime and matches how production operators like
cert-manager, Argo CD, and Flux are built.

### Industry standard for production operators

controller-runtime is the foundation of:
- **Kubebuilder** — the official Kubernetes operator scaffolding tool
- **Operator SDK** — Red Hat's operator framework
- **cert-manager**, **Argo CD**, **Flux**, **Crossplane** — all use controller-runtime

Using it ensures the codebase is recognisable to any engineer who has worked on
production Kubernetes operators.

### Acknowledged Trade-offs

| Trade-off | Impact | Mitigation |
|-----------|--------|------------|
| Less control over internals | Cannot tune cache behaviour as granularly | Acceptable for this operator's scale |
| controller-runtime abstraction hides client-go | Harder to learn client-go internals | Can drop down to client-go when needed |
| Framework version upgrades | Breaking changes between major versions | Pin to v0.17.0, upgrade deliberately |

## Consequences

**Positive:**
- 80% less boilerplate vs raw client-go for the same feature set
- Leader election, health probes, metrics are zero-config
- Code structure matches industry-standard operators (cert-manager, Argo CD)
- Any engineer familiar with Kubebuilder can contribute immediately

**Negative:**
- controller-runtime adds ~40MB to the module graph
- Some controller-runtime abstractions hide useful client-go internals
  (educational trade-off)

## Related

- `operator/controllers/flightroute_controller.go` — Reconcile loop
- `operator/main.go` — Manager setup
- [ADR-002](ADR-002-distroless-operator-image.md)
