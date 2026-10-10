# Operations Runbook: Ephemeral Environments & Virtual Clusters

## Objective
Provide platform engineers and on-call operators with diagnostics and resolution procedures for issues relating to ephemeral preview environments and virtual clusters (`vcluster`).

## Standard Operating Procedures

### 1. Inspect Active Ephemeral Environments
Execute the lifecycle manager in inspection mode:
```bash
python3 src/ephemeral_manager.py list
```
Or query Kubernetes namespaces directly:
```bash
kubectl get namespaces -l preview-env=true
kubectl get applications -n argocd -l preview-env=true
```

### 2. Manual Reaping of Stale Environments
If automated cron or webhook fails to clean up preview environments after PR closure:
```bash
# Run the reaper engine
python3 src/ephemeral_manager.py reap

# Force cleanup specific PR
python3 -c "from src.ephemeral_manager import EphemeralEnvironmentManager; EphemeralEnvironmentManager().destroy_preview_environment('org/repo', 42)"
```

### 3. Debugging vcluster Syncer Issues
If pods in the virtual cluster fail to schedule or services fail to map to the host cluster:
```bash
# Check the vcluster syncer pod logs in the host namespace
kubectl logs -n vcluster-pr-42 -l app=vcluster -c syncer --tail=100 -f

# Common failure: ResourceQuota exceeded in host namespace
kubectl describe resourcequota -n vcluster-pr-42
```

### 4. Resolving Ingress Conflicts
Preview environments dynamically claim hostnames like `pr-42.payments-api.preview.platform.corp`.
If duplicate hostnames occur:
```bash
kubectl get ingress -A | grep payments-api
```
Verify that the `NetworkPolicy` allows traffic from `ingress-nginx` namespace:
```bash
kubectl describe networkpolicy isolate-ephemeral-vcluster -n vcluster-pr-42
```
