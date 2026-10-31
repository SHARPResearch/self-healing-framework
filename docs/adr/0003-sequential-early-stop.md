# 0003. End a quarantine early only when the evidence is conclusive

Date: 2026-10-21. Status: Accepted.

## Context
Every quarantine waited a full lifecycle day (1,440 events) before deciding, so a legitimate
deployment kept alarming for that long.

## Decision
Look at 50% and 75% of the quarantine. Decide early only for the two outcomes that need no new
model:
- resume: the champion's alarm rate on the recent half has an exact one-sided Clopper-Pearson
  upper bound below the stale line;
- promote by re-baselining: only with a change event, champion still stale, tail not moving, and
  the re-baselined rate bounded below the line the full decision uses.

alpha = 0.05 per look and rule. Everything else waits the full length and decides as before.

## Alternatives considered
A stricter alpha (0.005) on the tail slice only: correct, but it never fired on SMD. Early
retraining: rejected, a challenger fitted on 360 rows of 38 metrics is not reliable.

## Consequences
Mean quarantine 1,440 to 1,172 events (-19%), no scenario significantly worse, 0 live incidents
learned (`RESULTS_COMPONENT2.md` section 11). Cost to watch: on held-out servers SMD's own drift
after a deployment drops 0.297 to 0.264 (p = 0.19); development servers showed the opposite, so the
rule was not tuned to it. On by default in ml-backend (`CADAL_EARLY_STOP`).
