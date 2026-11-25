# 0008. Label alarms after a pod restart as expected; do not suppress them

Date: 2026-10-31. Status: Accepted.

## Context
After a pod restart, memory and caches rebuild, and the detector alarms for minutes (0007). On the
live campaign 13 to 31% of the false alarms fell within 10 minutes after a restart. The decision
engine reads these alarms from the Redis stream and could remediate a pod that is only settling,
for example restart it again.

## Decision
For `RESTART_LABEL_SECONDS` (600 s) after a restart the backend reports reaches the service, every
`anomaly_score` message carries `context: "after_restart"`, the Logs line for an alarm episode says
it is expected, and the lifecycle card shows "Settling after a pod restart". Alarms are still
raised and scored exactly as before.

In live mode restarts come from the Kubernetes pod watcher (0007). The replay demo's Restart button
now sends a real `restart` event instead of a deployment event.

## Alternatives considered
- **Suppress alarms during the window.** Rejected: a restart caused by a real fault (an OOM loop, a
  crash on a bad request) must still alarm, and suppression would hide it.
- **Lower the alarm severity during the window.** Rejected for now: severity bands are shared with
  the decision engine, so changing their meaning per alarm needs that component's agreement. The
  label gives it the same information without changing the contract.

## Consequences
`context` is an additive field on `anomaly_score`; consumers that ignore it are unaffected. The
false-alarm count does not change; what changes is that a consumer can tell these alarms apart. In
replay, the Restart button now never promotes on any of the six demo services (before, Inventory
and Payments sometimes promoted a re-baselined model), and still resumes early on Search, Shipping
and Orders.
