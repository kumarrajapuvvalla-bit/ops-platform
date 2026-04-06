# Runbook: EKS Node Failure

**Severity:** P1
**Owner:** Platform Team
**Last Updated:** 2026-04-06

## Symptoms

- `eks_node_health_ratio` drops below 0.8 for a node group
- Pods stuck in `Pending` state across multiple deployments
- `FleetReadinessCritical` alert firing
- Cluster autoscaler logs show scale-up failures

## Immediate Actions (First 5 Minutes)

```bash
# 1. Check node status
kubectl get nodes -o wide

# 2. Identify unhealthy nodes
kubectl get nodes | grep -v Ready

# 3. Check node conditions
kubectl describe node <node-name> | grep -A 5 Conditions

# 4. Check node group in AWS console
aws eks describe-nodegroup \
  --cluster-name ops-platform-prod \
  --nodegroup-name ops-workers-prod \
  --region eu-west-2
```

## Diagnosis

```bash
# Check kubelet logs on the failing node (via SSM)
aws ssm start-session --target <instance-id>
sudo journalctl -u kubelet -n 100 --no-pager

# Check for disk pressure
kubectl describe node <node-name> | grep -i pressure

# Check for memory pressure
kubectl top nodes

# Check pending pods
kubectl get pods --all-namespaces | grep Pending
kubectl describe pod <pending-pod> -n <namespace>
```

## Resolution

### Option 1: Cordon and drain the node (preferred)
```bash
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data --grace-period=60
# AWS will replace the node automatically via node group health checks
```

### Option 2: Terminate and replace via ASG
```bash
aws autoscaling terminate-instance-in-auto-scaling-group \
  --instance-id <instance-id> \
  --should-decrement-desired-capacity false
```

## Escalation

- If >2 nodes fail simultaneously: escalate to P0, page on-call SRE
- If node group fails to replace: check EC2 capacity in the AZ, consider switching to a different instance type

## Post-Incident

- Create a postmortem in `postmortems/`
- Check if Cluster Autoscaler is running and healthy
- Review node group min/max sizing
