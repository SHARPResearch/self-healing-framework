# 0007. Restarts open a quarantine, explain the shift, and never license any repair

Date: 2026-10-31. Status: Accepted.

## Context
On the live Online Boutique campaign, alarms lingered after faults. Two things were behind it.
- **A restart was invisible.** A pod kill makes the ReplicaSet create a new pod, whose restart
  count starts at 0, so the `restarts` metric never moved; only out-of-memory kills raised it.
  The new pod's memory reset (cart: 52 MB to 17 MB) and climbed back over several minutes.
- **The campaign spacing.** Faults were 10 minutes apart with a 30-minute lifecycle day, so every
  quarantine held two or three faults and could only hold. That is a flaw of that campaign, not of
  CADAL, and needs a well-spaced campaign to measure.

## Decision
- A pod watcher (`change_events.PodRestartTracker`, `KubernetesPodWatcher`) emits `kind="restart"`
  change events: a pod replaced from a pod template already seen (killed or evicted; a new
  template is a rollout, reported by the Deployment watcher), or a container restart, with its
  exit reason (e.g. OOMKilled). Pods that existed before the watcher started are ignored.
- A restart opens a quarantine at once (trigger `restart`) but is not a licensing change
  (`LifecycleConfig.licensing_change_kinds` = deployment, config, scale).
- A quarantine that saw a restart, with no licensing change in its window, may only end in
  **resume** (the old model is quiet again, early if conclusive) or a new verdict **restart ->
  hold**. It never re-baselines, retrains or asks.

## Alternatives considered
- **Restart as an ordinary change event.** Rejected: it would license retraining on a warm-up.
- **Restart opens a quarantine but re-baselining stays allowed** (the first version). Tried on the
  recorded campaign and rejected: on cart it promoted a re-baselined model fitted to the post-restart
  memory level, which then alarmed more once memory recovered (false alarms 296 to 381 per hour,
  1 incident learned).
- **Suppressing alarms after a restart.** Not adopted: a restart caused by a real fault (an
  OOM loop) must still alarm. The serving layer labels such alarms instead (0008).

## Consequences
On the recorded campaign, with restarts reported: 0 incidents learned, false alarms unchanged from
the frozen model, decisions `restart -> hold` while settling and an early `resume` once settled.
13 to 31% of the false alarms fall within 10 minutes after a restart, which is the share the
dashboard and the decision engine can now see as expected. A level that stays changed after the pod
has warmed up is still learned, later, through the normal rules.
