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

Things worth trying next (out of scope for this Component 1 pass, left as follow-ups):
- Sweep `--eval-threshold` (e.g. 0.5, 0.6) — recall should rise as precision falls.
- Sweep `HST_N_TREES` / `HST_HEIGHT` / `HST_WINDOW_SIZE` in `.env`.
- Run across all 28 SMD entities and compare, rather than just `machine-1-1`.
- Compare against the NAB benchmark scorer per `docs/Doc1_Technical_Architecture.md` §9.

None of the above were done here — this file records what the current default configuration
actually produces, not a best-case result.
