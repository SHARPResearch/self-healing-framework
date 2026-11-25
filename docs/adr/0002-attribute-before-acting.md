# 0002. Attribute a shift before acting, instead of rolling back on every drift

Date: 2026-10-18. Status: Accepted.

## Context
The proposal's design rolled back to the last snapshot whenever ADWIN saw drift. Tested on 28 SMD
servers it never beat a frozen model: after a deployment the snapshot is the stale model.
Continuous learning absorbed long anomalies and lost recall in every variant.

## Decision
CADAL: on a drift, deployment or scheduled trigger, quarantine (keep serving, learn nothing),
measure label-free evidence on held-out events, and map it through fixed rules
(`drift_attribution.attribute`) to promote, hold, roll back, resume or ask the operator. Only a
change event licenses retraining; re-baselining (moving metric levels) is allowed without one.

## Alternatives considered
Naive rollback, periodic retraining, gated online learning, retraining without a change event.
All are ablations in `ml-pipeline/RESULTS_COMPONENT2.md` sections 1 and 2.

## Consequences
After a deployment MCC 0.144 vs 0.072 for a frozen model (p = 0.0005), never worse on undisturbed
data. A quarantine delays replacing a model (not detection) by up to one lifecycle day; 0003
shortens that when the evidence allows.
