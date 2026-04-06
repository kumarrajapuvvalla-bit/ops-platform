# Postmortem: INC-001 — Node Memory Pressure Cascade

**Date:** 2026-03-22
**Severity:** P1 (escalated to P0 briefly)
**Duration:** 1 hour 23 minutes (09:14 – 10:37 UTC)
**Author:** Kumar Raja Puvvalla
**Reviewers:** Platform Team
**Status:** Closed

## Summary

A noisy neighbour pod without resource limits caused memory exhaustion on
two of three worker nodes in the `ops-platform-prod` EKS cluster. This
triggered kubelet evictions, caused pod CrashLoopBackOff across fleet
services, and dropped the Fleet Readiness Score to 61% for 47 minutes.

## Severity

P1 (degraded service) — escalated to P0 at 09:31 UTC when Fleet Readiness
dropped below 80%. Downgraded back to P1 at 09:54 UTC after mitigation.

## Timeline (UTC)

| Time | Event |
|------|-------|
| 09:14 | Prometheus `NodeMemoryPressure` alert fires for `ip-10-0-2-44` |
| 09:16 | Second node `ip-10-0-2-87` enters MemoryPressure |
| 09:18 | Kubelet begins evicting pods on both nodes |
| 09:21 | Fleet Readiness Score drops below 95 — `FleetReadinessBreach` P1 fires |
| 09:24 | On-call engineer acknowledges page via PagerDuty |
| 09:28 | Investigation begins: `kubectl top nodes` shows 94% memory on two nodes |
| 09:31 | Fleet Readiness drops to 61% — alert escalates to P0 |
| 09:33 | Root cause identified: `data-pipeline-v2` pod consuming 6.2GB with no limits |
| 09:35 | `data-pipeline-v2` pod deleted and namespace quarantined |
| 09:38 | Memory pressure clears on both nodes |
| 09:45 | Evicted pods restart and pass readiness probes |
| 09:54 | Fleet Readiness Score recovers above 80% — downgraded to P1 |
| 10:37 | Fleet Readiness Score stable above 99% for 30 minutes — incident closed |

## Root Cause

A `data-pipeline-v2` pod deployed to the `data-team` namespace had no
`resources.limits.memory` set in its PodSpec. The pod loaded a large
dataset into memory, growing to 6.2GB, which caused the Linux OOM killer
to begin reclaiming memory across both nodes it was scheduled on.

```yaml
# Culprit PodSpec (simplified)
containers:
  - name: pipeline
    image: data-pipeline:v2.3.1
    # resources: {}   ← completely absent
```

## Contributing Factors

1. **No LimitRange in the `data-team` namespace** — allowed pods to be created without resource limits
2. **No admission webhook enforcing resource limits** — OPA/Gatekeeper was not configured to reject pods without limits
3. **Cluster Autoscaler did not scale out fast enough** — memory pressure appeared faster than new nodes could join (3 minutes)
4. **Alert-to-page latency was 7 minutes** — `NodeMemoryPressure` fired at 09:14 but on-call acknowledged at 09:24

## Resolution Steps Taken

```bash
# 1. Identified the offending pod
kubectl top pods --all-namespaces --sort-by=memory | head -5
# Output showed data-pipeline-v2 at 6.2Gi

# 2. Deleted the pod
kubectl delete pod data-pipeline-v2-7f8d9c-xkqzp -n data-team

# 3. Quarantined the namespace to prevent re-scheduling
kubectl label namespace data-team ops-platform/quarantine=true

# 4. Verified memory pressure cleared
kubectl get nodes
# All nodes showed Ready status within 4 minutes

# 5. Confirmed Fleet Readiness Score recovery
curl http://fleet-exporter.ops-platform-prod.svc.cluster.local:8000/metrics \
  | grep fleet_readiness_score
# fleet_readiness_score{environment="prod",cluster="ops-platform-prod"} 99.2
```

## Action Items

| # | Action | Owner | Due Date | Status |
|---|--------|-------|----------|--------|
| 1 | Add LimitRange to all namespaces with default memory limit of 512Mi | Platform | 2026-03-29 | ✅ Done |
| 2 | Deploy OPA/Gatekeeper policy to reject pods without resource limits | Platform | 2026-04-05 | ⏳ In Progress |
| 3 | Reduce PagerDuty alert-to-page latency from 7m to 2m | SRE | 2026-03-26 | ✅ Done |
| 4 | Add `NodeMemoryPressure` to Datadog monitor with 2m threshold | Observability | 2026-03-25 | ✅ Done |
| 5 | Configure Cluster Autoscaler to pre-emptively scale on 80% memory | Platform | 2026-04-12 | 🕒 Planned |
| 6 | Add postmortem link to Fleet Operations Grafana dashboard annotation | Observability | 2026-04-10 | 🕒 Planned |

## Lessons Learned

1. **Resource limits are not optional** — every pod in every namespace must have memory limits. A LimitRange and an admission webhook are both required; one alone is not enough.
2. **Alert detection was correct, response was slow** — the 7-minute acknowledge latency amplified blast radius. Stricter PagerDuty escalation policies are now in place.
3. **Blast radius was larger than expected** — we assumed node failure would be isolated; memory pressure affecting two nodes simultaneously is a credible failure mode that should be in our runbooks.
4. **The Self-Healing Operator worked correctly** — FlightRoute resources auto-healed their backing Deployments after evictions. HealCount on `LHR-JFK` reached 4 during the incident — this was expected behaviour.

## Fleet Readiness Score Chart

```
09:00  100.0 |██████████████████████████████
09:14   95.0 |                              █████
09:21   82.0 |                                   ███
09:31   61.0 |                                      ███
09:38   74.0 |                                         ███
09:54   83.0 |                                            ███
10:10   97.0 |                                               ███
10:37  100.0 |                                                  ███
```
