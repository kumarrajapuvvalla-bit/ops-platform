# Runbook: Failed Deployment Rollback

**Severity:** P1 (P0 if prod is affected)
**Owner:** Platform Team
**Last Updated:** 2026-04-06

## Symptoms

- Pods in `CrashLoopBackOff` after a deployment
- `p0_pod_crashloop` Datadog monitor firing
- ALB health check failures increasing
- `alb_target_healthy_ratio` dropping

## Immediate Actions

```bash
# 1. Check deployment status
kubectl rollout status deployment/<name> -n ops-platform-prod

# 2. Check recent events
kubectl get events -n ops-platform-prod --sort-by='.lastTimestamp' | tail -20

# 3. Check pod logs
kubectl logs -n ops-platform-prod -l app=<name> --previous --tail=100
```

## Rollback Procedure

### Via Helm (preferred)
```bash
# List recent releases
helm history ops-platform -n ops-platform-prod

# Rollback to previous revision
helm rollback ops-platform -n ops-platform-prod

# Verify rollback
kubectl rollout status deployment/<name> -n ops-platform-prod
```

### Via kubectl (emergency)
```bash
kubectl rollout undo deployment/<name> -n ops-platform-prod
kubectl rollout status deployment/<name> -n ops-platform-prod
```

## Verification

```bash
# Check pods are running
kubectl get pods -n ops-platform-prod

# Check Fleet Readiness Score recovered
curl http://fleet-exporter.ops-platform-prod.svc.cluster.local:9090/metrics | grep fleet_readiness

# Confirm ALB targets healthy
aws elbv2 describe-target-health --target-group-arn <arn>
```

## Root Cause Investigation

- Check GitLab pipeline logs for the failed deployment
- Review `kubectl describe pod` for OOMKilled or probe failures
- Check if Trivy scan was bypassed (should never be in prod)
