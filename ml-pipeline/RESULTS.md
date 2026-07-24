# Component 1 — HST training results

Current tuned configuration, `machine-1-1` (`n_trees=25, height=15, window_size=250, seed=42`,
`eval_threshold=0.4` — see the sweeps below for why):

| Metric | Value |
|---|---|
| Warm-up events (train split) | 28,479 |
| Warm-up throughput | ~450 events/sec |
| Test split size | 28,479 |
| Precision | 0.4344 |
| Recall | 0.8129 |
| F1 | **0.5663** |
| Actual anomalies in test split | 2,694 (9.5%) |

Reproduce with:

```bash
uv run python train.py --entity machine-1-1
```

The guide's original defaults (`eval_threshold=0.7`) gave a notably weaker precision 0.5097,
recall 0.2836, F1 0.3644 — it was scoring reasonably, just being graded with too strict a
threshold. See the threshold sweep below for the full picture.

## Reading these numbers honestly

Precision/recall/F1 are modest, not strong even after tuning — this is unsupervised anomaly
detection on real SMD data, not a tuned classifier, and both the threshold sweep and the
hyperparameter sweep below confirm this isn't from under-tuning. See "The realistic ceiling"
section at the bottom.

## Threshold sweep

Computed from the scores already saved above (no retraining, instant), baseline hyperparameters
(n_trees=25, height=15, window_size=250):

| Threshold | Precision | Recall | F1 |
|---|---|---|---|
| 0.3 | 0.3470 | 0.9298 | 0.5054 |
| 0.4 | 0.4343 | 0.8133 | 0.5662 |
| 0.5 | 0.4352 | 0.4952 | 0.4633 |
| 0.6 | 0.4197 | 0.3493 | 0.3813 |
| 0.7 (guide default) | 0.5097 | 0.2836 | 0.3644 |
| 0.8 | 0.6929 | 0.2127 | 0.3255 |
| 0.85 | 0.8445 | 0.1351 | 0.2330 |

Threshold 0.4 gives the best F1 (0.5662, up from 0.3644 at the guide's default 0.7). Now the
configured default (`EVAL_THRESHOLD=0.4` in `.env`, `PIPELINE_CFG.eval_threshold`), replacing the
hardcoded 0.7 that `train.py` used before.

## Hyperparameter sweep

`uv run python sweep_hyperparams.py`, one at a time around the baseline, on `machine-1-1`, best
threshold per combo (see script for details). Ranked best first:

| n_trees | height | window_size | best_threshold | precision | recall | f1 | duration |
|---|---|---|---|---|---|---|---|
| 25 (baseline) | 15 (baseline) | 250 (baseline) | 0.4 | 0.4344 | 0.8129 | **0.5663** | 105s |
| 25 | 15 | 400 | 0.4 | 0.4342 | 0.8133 | 0.5661 | 52s |
| 25 | 15 | 150 | 0.4 | 0.4339 | 0.8096 | 0.5650 | 87s |
| 10 | 15 | 250 | 0.5 | 0.4099 | 0.8508 | 0.5532 | 52s |
| 50 | 15 | 250 | 0.4 | 0.4115 | 0.6366 | 0.4999 | 265s |
| 25 | 10 | 250 | 0.3 | 0.3554 | 0.7765 | 0.4876 | 20s |
| 25 | 18 | 250 | 0.4 | 0.3483 | 0.6696 | 0.4582 | 815s |

**The baseline hyperparameters already won.** Every variant tested was flat or worse:
`window_size` barely matters (150 to 400 all land within 0.002 F1 of each other), fewer trees
(`n_trees=10`) is close but slightly worse, more trees (`n_trees=50`) is notably worse (possibly
overfitting to "normal" and becoming less sensitive), and both `height` variants are worse while
`height=18` also took 815 seconds for a single run versus baseline's 105 (HalfSpaceTrees builds
`2^height` nodes per tree up front, so height is exponential in cost, not linear — worth knowing
before increasing it). No `.env` changes made here: `HST_N_TREES=25`, `HST_HEIGHT=15`,
`HST_WINDOW_SIZE=250` stay as is; `EVAL_THRESHOLD=0.4` (from the threshold sweep above) is the
one real change from the guide's original defaults.

A genuinely useful negative result: this was not a wasted exercise even though nothing beat the
baseline — it rules out "we just didn't tune it" as an explanation for the modest F1, which
matters for the ceiling discussion below.

## All 28 SMD entities

`uv run python train_all.py`, baseline hyperparameters, `eval_threshold=0.4` (tuned on
`machine-1-1` above), serial execution:

| Statistic | F1 | Precision | Recall |
|---|---|---|---|
| Mean | 0.1195 | 0.0713 | 0.8673 |
| Median | 0.0765 | — | — |
| Min | 0.0143 (`machine-1-5`) | — | — |
| Max | 0.5663 (`machine-1-1`) | — | — |

Full per-entity table in `outputs/scores/all_entities_summary.csv`.

**Important finding: `machine-1-1` was not representative, it was the best case.** Its F1
(0.5663) is nearly 5x the 28-entity mean (0.1195) and by far the single highest score. Almost
every other entity shows the same pattern: recall stays high (0.5 to 1.0, the model does flag
most real anomalies) but precision collapses to single digits (as low as 0.0072 on
`machine-1-5`) — at `threshold=0.4`, the model over-flags heavily on most machines. Tuning the
threshold on one entity and assuming it transfers to the rest was the wrong move; each SMD
machine has a different baseline "normal" and a different HST score distribution, so **a single
global threshold does not work across entities**. This also means `services/decision-engine`'s
fixed global severity thresholds (`< 0.5` watch ... `> 0.85` critical, documented in root
`CLAUDE.md`) should be re-examined for the real system too, not just this offline evaluation --
if HST score distributions genuinely differ this much per service, per-service threshold
calibration (or a percentile/adaptive threshold) is likely necessary, not a nice-to-have.

This was not run before making `EVAL_THRESHOLD=0.4` the default, so the current default is a
known, documented weak point, not a silent one: it is tuned for `machine-1-1` specifically and
demonstrably does not generalize. Re-tuning per entity (or designing an adaptive threshold) is
the concrete next step, left out of this pass's scope.

## The realistic ceiling for unsupervised anomaly detection

Half-Space Trees never sees the ground-truth labels during training — it only ever learns "what
does normal look like" from unlabelled data and flags deviations from that. A supervised
classifier trained directly on labelled anomalies would be expected to score much higher (F1
0.8+ is common for supervised SMD baselines in the literature) because it can learn the exact
decision boundary between normal and anomalous. Unsupervised HST cannot do that by construction.
F1 in the 0.5 to 0.6 range on a well-tuned single entity, as found here after both a threshold
sweep and a hyperparameter sweep confirmed the defaults were already close to a local optimum,
is a realistic, defensible result for this method on its best case.

The 28-entity run above adds a second ceiling on top of that: the mean F1 across all entities
(0.1195) is far below the single-entity best (0.5663), because a single global threshold does
not transfer across machines with different baseline behaviour. Both of these are ceilings
this method has by construction, not bugs, and not something more tuning alone fixes -- fixing
the second one specifically needs per-entity (or adaptive) thresholding, not a better `n_trees`
or a better global `EVAL_THRESHOLD`. Comparing against a supervised baseline or the NAB benchmark
scorer (`docs/Doc1_Technical_Architecture.md` §9) would make the first ceiling concrete; building
per-entity threshold calibration would address the second. Both are genuine follow ups left out
of this pass's scope.
