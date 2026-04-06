# Postmortem: Fleet Readiness Score Dropped to 78% — 2026-03-15

**Severity:** P0
**Duration:** 47 minutes (14:22 – 15:09 UTC)
**Impact:** Fleet readiness score dropped to 78%, triggering 3 Datadog P0 alerts. All FlightRoute SLOs breached for 47 minutes.

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 14:22 | Automated deployment of v2.1.4 begins in prod |
| 14:24 | ALB target health drops — new pods failing readiness probes |
| 14:25 | `FleetReadinessCritical` alert fires, pages on-call |
| 14:27 | On-call acknowledges — begins investigation |
| 14:31 | Root cause identified: new env var `SCRAPE_INTERVAL` required but missing from Helm values |
| 14:35 | Helm rollback initiated |
| 14:38 | Pods recover, ALB targets healthy |
| 15:09 | Fleet readiness confirmed back above 99.5%, incident closed |

## Root Cause

A new required environment variable (`SCRAPE_INTERVAL`) was added to `fleet_exporter.py` but not added to the Helm chart values or the GitLab CI deploy stage. The container started but immediately exited with a `KeyError`.

## Contributing Factors

1. No integration test validated the new env var end-to-end before prod deploy
2. The `SCRAPE_INTERVAL` variable had a default in dev but not prod values file
3. Readiness probe timeout (30s) was too long — delayed detection by ~6 minutes

## Action Items

| Action | Owner | Due |
|--------|-------|-----|
| Add env var validation to container startup (`assert` all required vars) | Platform | 2026-03-22 |
| Reduce readiness probe initial delay to 10s in prod | Platform | 2026-03-19 |
| Add integration test that boots the container and hits `/metrics` | CI/CD | 2026-03-25 |
| Update Helm chart to fail loudly on missing required values | Platform | 2026-03-22 |

## Lessons Learned

- Required env vars should be validated at startup, not at first use
- Integration tests need to cover the deployed container, not just unit tests
- Readiness probe delays hide problems in prod for too long
