# 0009. Run ml-backend in the cluster as one replica, Ready only after its warm-up

Date: 2026-11-21. Status: Accepted.

## Context
Until now ml-backend only ran on the laptop (uvicorn, port 8002), reading the cluster through a
Prometheus port-forward and the `sharp` kubeconfig context. None of our own services ran in
Kubernetes, and the Helm chart had placeholder templates only. To be deployable, the backend has
to run as a pod next to what it monitors, with only the permissions it needs.

The backend is stateful: each service's detector, its CADAL quarantine buffer and its model
versions live in the process. Two copies would each score every service, open their own
quarantines and write different lifecycle decisions about the same model.

## Decision
- The chart (`infrastructure/helm/self-healing-framework`) installs ml-backend into
  `selfheal-system` (the namespace Doc1 §8 names), with TimescaleDB (StatefulSet, 2 Gi volume)
  and Redis. The image is `services/ml-backend/Dockerfile`; `deploy-sharp.ps1` builds it, loads it
  into minikube and installs the release.
- **One replica, `Recreate` strategy.** A rollout stops the old pod (which writes every
  checkpoint on shutdown, 0005 and 0006) before the new one starts and restores them.
- **Ready means scoring.** `/api/ready` returns 503 until the fleet has warmed up on Prometheus
  history; `/api/health` answers from the first second and is the liveness probe. The fleet is
  built in the background and retried every 30 s, so a pod started before Prometheus has enough
  history, or before it is reachable at all, waits instead of crash looping.
- **Least privilege.** A Role in the monitored namespace only: watch Deployments and Pods (change
  and restart events), patch Deployments (the Rollout and Traffic actions) and create, list and
  delete the three Chaos Mesh kinds the dashboard injects. Chaos actions can be switched off
  (`mlBackend.rbac.chaosActions=false`) for a production cluster.
- Non-root (uid 10001), read-only root filesystem with an emptyDir `/tmp`, all capabilities
  dropped, RuntimeDefault seccomp. The backend writes nothing to disk: the registry is in memory
  and persisted to TimescaleDB.

## Alternatives considered
- **Several replicas behind the Service.** Rejected: duplicate decisions, as above. Scaling out
  means sharding services across replicas (each owns a subset), which the scalability benchmark
  supports (35k to 70k events/s over 1 to 4 workers) but which needs a shard assignment and a
  fan-in for the dashboard. Not needed at Online Boutique's 11 services.
- **Leader election with hot standbys.** Rejected for now: the checkpoint restore already makes a
  restart cheap (about 8 KB of state per service), so a standby saves seconds, not minutes.
- **Keep the laptop process and only containerise the stores.** Rejected: it leaves the
  component undeployable, which is the gap this closes.

## Consequences
Availability is that of one pod: during a restart nothing is scored for the seconds it takes to
start and restore. A restored service continues where it was; an unrestorable one warms up again.
The decision engine and the gateway still have no templates; their owners add them to the same
chart.
