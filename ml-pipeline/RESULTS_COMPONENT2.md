# Component 2 results: dynamic model updating (CADAL) on SMD

28 SMD entities x 4 drift scenarios x 8 policies = 896 runs, one seed, produced by
`evaluate_dynamic.py` and `summarize_dynamic.py`. machine-1-1 was the development entity (the design
was debugged on it), so every claim below that matters is also stated on the **27 held-out
entities**. All tests are paired two-sided Wilcoxon signed-rank over entities. **No correction for
multiple comparisons was applied**: treat p-values between 0.01 and 0.05 as suggestive.

Scenarios: `none` (original SMD), `deploy` (two injected persistent level shifts of +0.2 to 0.3 on
30% of features, each announced by a deployment change event), `silent` (same shifts, no event),
`noop_deploy` (deployment events but no behaviour change). Labels are untouched by the injection.

Policies: `static` (frozen after warm-up), `online` (learn every event), `gated` (learn only
non-alarms), `naive_rollback` (the original design: any ADWIN drift restores the last stable
snapshot), `periodic` (scheduled retrain), `cadal` (proposed), `cadal_no_events` (no change prior),
`cadal_online` (cadal with gated continuous learning).

## Headline

1. **Against the static baseline, CADAL does not improve F1 or MCC.** Mean F1 is 0.155 vs 0.145
   (deploy), 0.136 vs 0.145 (silent), 0.190 vs 0.189 (none); none of these differences is
   significant (all p > 0.12). The proposal's core hypothesis, "the dynamic model maintains
   consistently higher F1 than the static baseline", is **not supported** by this evaluation.
2. **What CADAL does change is the error profile after drift.** On the held-out entities the static
   model's post-drift false-alarm rate on normal points is 0.51; CADAL's is 0.17 (p < 0.0001; CADAL's
   rate is lower on 20 of 27 entities, equal on 7, higher on none). The price is recall: post-drift recall falls from 0.68 to
   0.39 (p < 0.0001). F1 nets out roughly even because the gain in precision cancels the loss
   in recall. Whether that trade is worth it depends on the cost of alert fatigue, which this
   evaluation cannot measure.
3. **CADAL beats the other adaptive policies.** The original rollback design (`naive_rollback`) is
   clearly worst after deployments. CADAL's F1 is higher by +0.066 on all 28 entities (p = 0.038);
   on the 27 held-out ones the gap is +0.061 but p = 0.066, so that comparison is suggestive, not
   established. Naive rollback is the policy the guide originally specified, so this
   is the most defensible positive result.
4. **The change-event prior helps when drift is announced and does no measurable harm when it is not.**
   `cadal` vs `cadal_no_events` on deploy: F1 +0.019 (p = 0.008; held-out +0.019, p = 0.016), MCC +0.023
   (p = 0.021). On `noop_deploy` the difference is -0.002 (p = 0.56). On `silent` they are identical by
   construction (no events exist).
5. **Absolute detection quality is low for every policy** (best mean F1 about 0.19). This is
   Component 1's ceiling (`RESULTS.md`), not something lifecycle management can lift. FR7
   (F1 >= 0.65) is not achievable with this detector.

## Mean metrics (28 entities)

| scenario | policy | F1 | MCC | recall | false-alarm rate | post-drift F1 | post-drift FA rate | recovery (events) |
|---|---|---|---|---|---|---|---|---|
| deploy | static | 0.145 | 0.137 | 0.578 | 0.349 | 0.152 | 0.523 | 454 (18/28 recover) |
| deploy | online | 0.091 | 0.080 | 0.175 | 0.047 | 0.093 | 0.058 | 386 |
| deploy | gated | 0.118 | 0.102 | 0.304 | 0.151 | 0.119 | 0.208 | 630 (25/28) |
| deploy | naive_rollback | 0.089 | 0.071 | 0.240 | 0.122 | 0.094 | 0.173 | 667 (25/28) |
| deploy | periodic | 0.097 | 0.088 | 0.351 | 0.131 | 0.108 | 0.157 | 849 |
| deploy | cadal_online | 0.124 | 0.106 | 0.332 | 0.127 | 0.125 | 0.169 | 1112 |
| deploy | cadal_no_events | 0.136 | 0.122 | 0.313 | 0.125 | 0.143 | 0.176 | 1150 |
| deploy | **cadal** | **0.155** | **0.146** | 0.347 | 0.120 | 0.165 | 0.169 | 1012 |
| none | static | 0.189 | 0.199 | 0.314 | 0.085 | n/a | n/a | n/a |
| none | **cadal** | 0.190 | 0.201 | 0.280 | 0.050 | n/a | n/a | n/a |
| none | naive_rollback | 0.114 | 0.113 | 0.187 | 0.052 | n/a | n/a | n/a |
| none | online | 0.125 | 0.124 | 0.176 | 0.031 | n/a | n/a | n/a |
| silent | static | 0.145 | 0.137 | 0.578 | 0.349 | 0.152 | 0.523 | 454 |
| silent | cadal | 0.136 | 0.122 | 0.313 | 0.125 | 0.143 | 0.176 | 1150 |
| noop_deploy | static | 0.189 | 0.199 | 0.314 | 0.085 | 0.202 | 0.111 | 269 |
| noop_deploy | cadal | 0.187 | 0.191 | 0.281 | 0.057 | 0.203 | 0.072 | 268 |

Recovery is the number of events after the first injected drift until the rolling false-alarm rate on
normal points is back under 2x the target rate (3%). CADAL recovers on all 28 entities in the deploy
scenario but slower than static where static does recover (it waits a day of evidence before
adapting); static never recovers on 10 of 28 entities.

## Where CADAL helps and hurts (deploy, post-drift F1, per entity)

Largest losses vs static: machine-1-6 (0.47 to 0.24), machine-3-3 (0.08 to 0.01), machine-2-1 (0.13
to 0.07). Largest gains: machine-3-8 (+0.16), machine-3-6 (+0.09), machine-3-10 (+0.08). Across
all 28 entities it is 16 wins, 7 ties, 5 losses for post-drift F1 (mean +0.013, p = 0.06); the
effect is concentrated in a few entities. I did not investigate why CADAL loses on the entities
where it does (machine-1-6 is the one to look at first).

## Lifecycle decisions (cadal, summed over 28 entities)

| scenario | concept drift (promote) | incident (hold) | model decay (rollback) | no change (resume) |
|---|---|---|---|---|
| none | 32 | 18 | 2 | 284 |
| deploy | 60 | 21 | 2 | 211 |
| silent | 56 | 21 | 1 | 223 |
| noop_deploy | 32 | 14 | 4 | 275 |

The injected shifts roughly double the promotions (32 to 60), consistent with the mechanism firing on
the injected drift (two injections per entity = 56 expected). The 32 promotions in the
undisturbed `none` scenario are natural SMD drift that CADAL also adapts to (about one per
entity). Rollback is rare (0.08 per run), as designed: the original design's 82 rollbacks per run
were almost all unnecessary. Some of the 18 to 21 holds will be false incidents. This evaluation
cannot say how many, because SMD's labelled anomalies do not mark when a "new normal" begins.

## Latency and requirements FR3 / FR6

| policy | mean ms/event | p99 ms/event | worst p99 over entities |
|---|---|---|---|
| static | 0.23 | 0.67 | 7.7 |
| cadal | 0.73 | 0.52 | 3.8 |
| online / gated | 2.0 / 1.8 | 1.5 / 1.6 | 17.7 / 19.2 |
| naive_rollback | 2.2 | 2.4 | 31.3 |

- **FR6 (<= 5 ms added per event): met for CADAL** (worst-entity p99 3.8 ms). Policies that learn on
  every event are slower and spike higher. Timings are from a laptop sharing CPU with a second
  worker, so absolute values are pessimistic.
- **FR3 (rollback within one scoring cycle): met for the rollback itself, not for the quarantine
  close.** Restoring a snapshot takes about 37 ms and CADAL's rollbacks are rare. But *closing a
  quarantine* (fitting the challenger on up to 1,440 events) blocks the scoring loop for a median
  of 1.3 s, p95 2.5 s, max 8.7 s. In production this must run off the scoring path (a background
  task that swaps the model when ready). It is **not implemented**, and the numbers above include
  this blocking.

## Ablations

- **Frozen vs gated continuous learning** (`cadal` vs `cadal_online`): frozen is ahead on average
  (deploy F1 +0.031, none +0.042) but only the `none`-scenario MCC difference is significant
  (p = 0.010). It is also faster by about 2.6x. The "continuous learning hurts HST on SMD" claim rests on
  this plus the `online` and `gated` rows, and should be worded as "did not help", not "hurts".
- **Drift detector** (Page-Hinkley, KSWIN): variants exist (`cadal_page_hinkley`, `cadal_kswin`)
  but **have not been run**.

## Threats to validity and limits

- One seed for the drift injection; no confidence intervals over seeds.
- Synthetic drift (level shifts) is the only benign drift tested; real deployments also change
  correlations and variance.
- machine-1-1 was used for development; the design constants (quarantine length, gate percentile,
  null quantile) were chosen on it plus the synthetic tests. Held-out numbers are given above.
- No multiple-comparison correction; 40+ paired tests were run.
- The undisturbed `none` scenario is not drift-free: SMD drifts naturally, and CADAL acts on it.
- NAB scoring and the supervised-upper-bound comparison are not included.
- A day-long quarantine means CADAL reacts about one day after a shift. That suits the stated
  problem (baseline change after deployments) but not fast-moving incidents, which are
  the detector's job, not the lifecycle manager's.
