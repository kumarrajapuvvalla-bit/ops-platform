# Runbook: High Latency Incident

**Severity:** P1
**Owner:** Platform Team
**Last Updated:** 2026-04-06
**Datadog Runbook Link:** `https://app.datadoghq.eu/monitors/runbook?id=high-latency-fleet`

## Summary

This runbook covers P1 response for elevated latency across fleet services.
High latency is defined as p99 response time > 500ms sustained for 5 minutes
or ALB 5xx error rate > 5% for 2 minutes.

## Severity

| Condition | Severity |
|-----------|----------|
| p99 > 500ms for 5m, no user impact | P2 |
| p99 > 1000ms for 5m, partial user impact | P1 |
| p99 > 2000ms or total service unavailability | P0 |

## Detection

- **Datadog monitor:** `[P1] High ALB Latency` — fires when `aws.applicationelb.target_response_time.p99 > 1`
- **Prometheus alert:** `FleetReadinessBreach` — score < 95 for 5m
- **Grafana dashboard:** Fleet Operations — `Error Rate` panel turns red
- **User reports:** Slack `#ops-alerts` channel

## Customer Impact

- Flight booking requests may time out or return 504 errors
- Check-in kiosks may be slow or unresponsive
- Payment processing delays possible (but usually isolated to payment-svc)

## Investigation Steps

### Step 1: Identify the slow pods

```bash
# Get pods with high CPU or memory
kubectl top pods -n ops-platform-prod --sort-by=cpu | head -20

# Check pod events for OOMKilled or failed probes
kubectl get events -n ops-platform-prod --sort-by='.lastTimestamp' \
  | grep -E 'Warning|OOMKill' | tail -20

# Describe a specific slow pod
kubectl describe pod <pod-name> -n ops-platform-prod
```

### Step 2: Check ALB target health

```bash
# List all target groups
aws elbv2 describe-target-groups \
  --query 'TargetGroups[*].[TargetGroupName,LoadBalancerArns]' \
  --output table \
  --region eu-west-2

# Check target health for a specific TG
aws elbv2 describe-target-health \
  --target-group-arn <arn> \
  --region eu-west-2 \
  --query 'TargetHealthDescriptions[*].[Target.Id,TargetHealth.State,TargetHealth.Description]' \
  --output table
```

### Step 3: Check Datadog APM for slow traces

```bash
# Datadog CLI (if installed)
datadog-ci traces search \
  --service fleet-exporter \
  --env prod \
  --min-duration 1000 \
  --limit 20
```

### Step 4: Check application logs for errors

```bash
# CloudWatch logs (ECS)
aws logs filter-log-events \
  --log-group-name /ecs/fleet-exporter/prod \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s000) \
  --region eu-west-2 \
  --query 'events[*].message' \
  --output text | head -30

# Kubernetes pod logs
kubectl logs -n ops-platform-prod \
  -l app.kubernetes.io/component=fleet-exporter \
  --since=30m | grep -E 'ERROR|WARNING' | tail -50
```

### Step 5: Check EKS node resource pressure

```bash
# Check node conditions
kubectl get nodes -o custom-columns=\
  'NAME:.metadata.name,STATUS:.status.conditions[-1].type,CPU:.status.capacity.cpu,MEM:.status.capacity.memory'

# Check for resource-constrained pods
kubectl describe nodes | grep -A 5 'Allocated resources'
```

## Resolution

### Option A: Scale out the affected deployment

```bash
# Increase replicas temporarily
kubectl scale deployment <deployment-name> \
  --replicas=<current+2> \
  -n ops-platform-prod

# Or via Helm (preferred — keeps state consistent)
helm upgrade ops-platform helm/ops-platform/ \
  -n ops-platform-prod \
  --set fleetExporter.replicaCount=4 \
  --reuse-values
```

### Option B: If a specific pod is causing slowness

```bash
# Delete the pod — Deployment will recreate it
kubectl delete pod <pod-name> -n ops-platform-prod

# Monitor replacement pod startup
kubectl get pods -n ops-platform-prod -w
```

### Option C: Roll back last deployment if latency started post-deploy

```bash
# Check Helm history
helm history ops-platform -n ops-platform-prod

# Roll back to previous revision
helm rollback ops-platform -n ops-platform-prod

# Verify
kubectl rollout status deployment/ops-platform-exporter -n ops-platform-prod
```

## Rollback Decision Tree

```
Latency spike started after deployment?
  YES → helm rollback ops-platform (Option C)
  NO  → Is a specific pod the culprit?
          YES → kubectl delete pod <name> (Option B)
          NO  → Is overall cluster under load?
                  YES → Scale out (Option A)
                  NO  → Escalate to P0, page on-call SRE
```

## Post-Incident

1. Create postmortem in `postmortems/` within 24 hours
2. Verify Fleet Readiness Score returns above 95
3. Check if HPA kicked in — if not, review HPA configuration
4. Add/update alert thresholds if detection was late

## Owner

**On-call rotation:** `platform-sre` PagerDuty service
**Escalation:** `#platform-team` Slack, then `@platform-lead`
