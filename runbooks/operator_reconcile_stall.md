# Runbook: Operator Reconcile Stall

**Severity:** P2
**Owner:** Platform Team
**Last Updated:** 2026-04-06

## Symptoms

- `OperatorReconcileLag` alert firing
- FlightRoute resources stuck in `Progressing` state
- `kubectl get flightroutes` shows stale `currentReplicas`
- Self-healing not triggering despite replica drift

## Diagnosis

```bash
# Check operator pod status
kubectl get pods -n ops-platform -l app=ops-operator

# Check operator logs
kubectl logs -n ops-platform -l app=ops-operator --tail=200

# Check leader election
kubectl get lease -n ops-platform

# List all FlightRoutes and their status
kubectl get flightroutes --all-namespaces
kubectl describe flightroute lhr-jfk
```

## Resolution

```bash
# Restart the operator (safe — leader election handles failover)
kubectl rollout restart deployment/ops-operator -n ops-platform

# Monitor reconcile loop recovery
kubectl logs -n ops-platform -l app=ops-operator -f | grep -i reconcil

# Verify FlightRoutes are reconciling
kubectl get flightroutes --all-namespaces -w
```

## If restart does not resolve

```bash
# Delete the leader election lease to force re-election
kubectl delete lease ops-platform-operator.kumarrajapuvvalla-bit.github.io -n ops-platform

# Scale down and back up
kubectl scale deployment/ops-operator -n ops-platform --replicas=0
kubectl scale deployment/ops-operator -n ops-platform --replicas=2
```
