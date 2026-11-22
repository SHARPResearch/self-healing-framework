# 0006. Store lifecycle checkpoints in TimescaleDB; on in live mode, off for the replay demo

Date: 2026-10-31. Status: Accepted.

## Context
0005 made a service's lifecycle state exportable. The backend needs somewhere durable to keep it,
a rule for when to write it, and a rule for when a saved checkpoint may be used.

## Decision
- **Where.** One row per service in `model_checkpoints` (`infrastructure/local/init.sql`): the
  compressed blob plus `source`, `step` and `production_version`. About 8 KB per service on SMD.
  TimescaleDB is already the backend's store of record, so no new dependency.
- **When written.** A service is marked dirty whenever its lifecycle emits anything (a transition,
  version, decision or query). Dirty services are saved every 30 s, every service every 5 min,
  and all of them on shutdown. Saves happen between scoring steps, under the step lock.
- **When used.** At startup a checkpoint is restored only for the same service id, the same
  `source` (SMD machine, or namespace/deployment), the same detector and the same features.
  Anything else warms up from scratch. A damaged checkpoint is logged and ignored.
- **Mode.** `MODEL_CHECKPOINTS=auto` (default) enables it in live mode only. The replay demo is
  meant to start from its warm-up every time, so it stays off there unless set to `on`. A demo
  reset clears all checkpoints.
- **Live warm-up.** A live service with a checkpoint resumes at once; only services without one
  fetch the hour of Prometheus history.

## Alternatives considered
- Saving after every event: thousands of writes a second in replay, for no benefit.
- Saving only on shutdown: a crash or an OOM kill would lose everything since the last start.
- MLflow artifacts: see 0005.

## Consequences
Up to 30 s of lifecycle changes can be lost on a hard crash; a promotion lost that way is decided
again by the next quarantine. The registry keeps every version it ever made, so a checkpoint grows
with time (scheduled validity checks add a version every two lifecycle days). Bounding that is
tracked separately.
