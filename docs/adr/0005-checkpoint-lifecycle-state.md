# 0005. Persist each service's lifecycle state and restore it on restart

Date: 2026-10-31. Status: Accepted.

## Context
Every model version, threshold, re-baselining shift and open operator question lived only in the
backend's memory. A restart or a new pod re-warmed every service: promoted versions were lost, a
question an operator was about to answer vanished, and in live mode a restart needed a clean hour
of Prometheus history before scoring again.

## Decision
`DynamicModelManager.export_state()` writes one compressed JSON checkpoint per service:
- the whole registry: versions as HSTState snapshots, the production pointer, the audit trail;
- the serving threshold, learning gate and re-baselining state;
- the per-service null floors, cooldowns, and operator queries, including the validated candidate
  an open question is waiting on.

`restore_state()` applies it instead of a warm-up, and refuses a checkpoint made for another
detector configuration or another feature set. An open quarantine and the drift detector's window
are not saved: after a restore the service is stable, and a shift that is still there reopens a
quarantine on its own.

## Alternatives considered
- MLflow as the only store: it keeps model versions but not the lifecycle's own state (null floors,
  cooldowns, open questions), and puts a network dependency on every restart.
- Pickling the manager: ties the format to class internals and is unsafe to load.

## Consequences
A restart resumes where the service was. A checkpoint is only valid for the same detector and
features, so changing either re-warms that service, by design. The backend stores and loads them
(0006).
