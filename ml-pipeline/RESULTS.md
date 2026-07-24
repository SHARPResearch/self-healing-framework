# Component 1 — HST training results

Verified run, `machine-1-1`, default hyperparameters (`n_trees=25, height=15, window_size=250,
seed=42`, eval threshold `0.7`):

| Metric | Value |
|---|---|
| Warm-up events (train split) | 28,479 |
| Warm-up throughput | ~450 events/sec |
| Test split size | 28,479 |
| Mean test anomaly score | 0.213 |
| Precision | 0.5097 |
| Recall | 0.2836 |
| F1 | 0.3644 |
| Actual anomalies in test split | 2,694 (9.5%) |

## Reading these numbers honestly

Precision/recall/F1 are modest, not strong — this is unsupervised anomaly detection with
out-of-the-box hyperparameters on real SMD data, not a tuned classifier. At `threshold=0.7`
the model is conservative (fewer false positives, more missed anomalies — recall 0.28 confirms
it misses most true anomalies). Reproduce with:

```bash
uv run python train.py --entity machine-1-1 --eval-threshold 0.7
```

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

## Things worth trying next

- Sweep `HST_N_TREES` / `HST_HEIGHT` / `HST_WINDOW_SIZE` in `.env` (see next section once done).
- Run across all 28 SMD entities and compare, rather than just `machine-1-1` (see next section).
- Compare against the NAB benchmark scorer per `docs/Doc1_Technical_Architecture.md` §9 (not
  done here, left as a genuine follow up beyond this pass's scope).
