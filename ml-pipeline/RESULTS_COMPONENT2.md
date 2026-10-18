# Component 2 results: dynamic model updating (CADAL)

Final evaluation of the improved system. The first evaluation (git history of this file) found that
CADAL did not beat a static model. The diagnosis of why led to the changes listed at the end. This
file reports the final configuration only, with every claim tested on data that was not used to
design it.

**Final configuration.**
- Component 1 detector: PCA reconstruction error, EWMA-smoothed over 5 events
  (`detector_config("pca_s5")`), calibrated per version with Peaks-Over-Threshold at risk 0.01.
- Component 2: CADAL with frozen serving, re-baselining, the change-licensed retrain rule and
  per-entity null floors (`LifecycleConfig(threshold_method="pot")`).

**Protocol.**
- Development data: the 8 SMD `machine-1-*` entities. Every design choice was made on them.
- Held-out data: the other 20 SMD entities, all of NAB, all of RCAEval.
- Labels are never seen by any lifecycle decision; they are only used to score the alarms
  afterwards.
- Statistics are paired two-sided Wilcoxon signed-rank tests over entities, with no
  multiple-comparison correction, so read p between 0.01 and 0.05 as suggestive.
- Metrics:
  - MCC is primary. F1 rewards a stale model that alarms on everything when anomalies are
    frequent, while MCC is 0 for any constant predictor.
  - Informedness J = recall − false-alarm rate measures detection skill above chance.

Scenarios (SMD test split, 28,479 one-minute events per entity):

| scenario | what happens | what it tests |
|---|---|---|
| `none` | original data | no harm when nothing is injected (SMD still drifts naturally) |
| `deploy` | two persistent level shifts (+0.2 to 0.3 on 30% of metrics), each announced by a deployment event | adaptation to a deployment that changes the baseline |
| `silent` | the same shifts, no event | adaptation to an unexplained baseline change |
| `noop_deploy` | deployment events, no injected change | not replacing a model for nothing, and adapting to SMD's **real** drift when an event allows it |

Policies: `static` (frozen), `naive_rollback` (the original design: every ADWIN drift restores the
last stable snapshot), `periodic` (blind retrain every 2 days), `cadal` (proposed), and the
ablations `cadal_no_events`, `cadal_retrain_only` (no re-baselining) and `cadal_retrain_free`
(retrain without a change event).

## 1. Does dynamic updating beat a static model? (SMD, `outputs/final/smd_pca_pot/`)

MCC, CADAL vs static, same detector:

| scenario | all 28: CADAL vs static | wins / ties / losses | p | held-out 20: CADAL vs static | W/T/L | p |
|---|---|---|---|---|---|---|
| none | 0.280 vs 0.274 | 5 / 23 / **0** | n/a | 0.250 vs 0.243 | 4 / 16 / **0** | n/a |
| deploy | **0.144 vs 0.072** | 22 / 1 / 5 | **0.0005** | **0.128 vs 0.074** | 15 / 1 / 4 | **0.016** |
| deploy, after the shift only | **0.107 vs −0.001** | 23 / 1 / 4 | **< 0.0001** | **0.091 vs 0.000** | 15 / 1 / 4 | **0.002** |
| silent | 0.096 vs 0.072 | 11 / 13 / 4 | 0.17 | 0.078 vs 0.074 | 7 / 10 / 3 | 0.56 |
| noop_deploy (real SMD drift) | **0.313 vs 0.274** | 12 / 9 / 7 | **0.049** | **0.297 vs 0.243** | 10 / 5 / 5 | **0.026** |

F1 tells the same story:
- deploy: 0.152 vs 0.097, p = 0.0001;
- silent: 0.115 vs 0.097, p = 0.03;
- noop_deploy: 0.293 vs 0.255, p = 0.049.

Reading it:
- **No harm.** On undisturbed data CADAL never makes an entity worse than static (0 losses in 28).
- **After a deployment it restores a working detector.** The static model's post-shift MCC is
  ~0 because it alarms on 99.5% of normal points. CADAL brings post-shift MCC to 0.107 and cuts
  the false-alarm rate to 0.39.
- **On SMD's own drift it improves prediction.** In `noop_deploy` nothing is injected. The
  deployment events let CADAL replace models that SMD's real train-to-test drift had made stale,
  and it beats static on held-out entities (p = 0.026). This is the "real data point" for dynamic
  updating on SMD.
- **Unannounced drift is the weak spot.** Without a change event, re-baselining is the only
  repair allowed, and it rarely restores a PCA model after these clipped level shifts. Post-shift
  false alarms stay at 0.76.

Against the other adaptive policies (all 28 entities, MCC):

| | none | deploy | silent | noop_deploy | mean |
|---|---|---|---|---|---|
| static | 0.274 | 0.072 | 0.072 | 0.274 | 0.173 |
| naive_rollback (original design) | 0.273 | 0.072 | 0.072 | 0.273 | 0.173 |
| periodic | 0.169 | **0.147** | **0.147** | 0.169 | 0.158 |
| **cadal** | **0.280** | 0.144 | 0.096 | **0.313** | **0.208** |

- The original rollback design never helps. It restores a snapshot of the same stale model.
- Blind periodic retraining is the best policy after an unannounced shift, but costs 40% of the
  MCC on undisturbed data (0.169 vs 0.280, p = 0.03), because it keeps replacing good models
  with ones fitted on two days. CADAL has the best mean.

## 2. Ablations (all 28 entities, MCC)

| variant | none | deploy | silent | noop_deploy | what it shows |
|---|---|---|---|---|---|
| cadal | 0.280 | 0.144 | 0.096 | 0.313 | |
| cadal_no_events | 0.280 | 0.096 | 0.096 | 0.280 | change events drive the deploy and noop gains |
| cadal_retrain_only | 0.274 | 0.139 | 0.072 | 0.311 | re-baselining is what helps on silent drift at all |
| cadal_retrain_free | 0.236 | 0.124 | 0.117 | 0.264 | retraining without a change event fixes more silent drift but also "adapts" to incidents and costs 0.044 MCC on undisturbed data |

The retrain-without-event trade-off goes the other way on NAB (section 3), so it is a policy
choice, not a settled result.

## 3. Real public data beyond SMD

**NAB, 46 real cloud and traffic series with labelled anomaly windows** (`outputs/nab/`).
- These series have real, unlabelled regime changes and no deployment logs, so no change event
  ever fires.
- PCA is degenerate on univariate series, so NAB uses the HST + robust-z ensemble.
- All settings derive from the SMD defaults and the sampling rate; nothing is tuned on NAB.

| policy | MCC | false-alarm rate | p vs static |
|---|---|---|---|
| static | 0.096 | 0.093 | |
| naive_rollback | 0.088 | 0.051 | |
| periodic | 0.095 | 0.119 | |
| cadal | 0.106 | 0.084 | 0.40 (21 W / 15 L) |
| cadal_retrain_free | **0.131** | **0.049** | 0.062 (25 W / 13 L); vs naive_rollback p = 0.013 |

- With no change events, CADAL can only re-baseline, and its gain over static is small and not
  significant.
- Allowing retraining without an event is the best NAB policy. On SMD that same setting hurt
  undisturbed data (section 2).

**RCAEval, 250 real fault injections in Online Boutique and Sock Shop on Kubernetes**
(`outputs/rcaeval/`). This is the Component 1 evaluation; the cases are 12 to 70 minutes long,
too short for lifecycle drift. On Online Boutique the selected detector catches 100% of faults
with a 2-second median delay, and its MCC is 0.700 vs 0.368 for HST (p ≈ 5e-12). Details are in
`RESULTS.md`, "Detector v3".

## 4. What the improved Component 1 contributes (`outputs/final/smd_river/`)

The whole new system against Component 1 as shipped (river HST, 97th percentile), all 28
entities, MCC:

| | none | deploy | silent | noop_deploy | mean |
|---|---|---|---|---|---|
| river HST, static (shipped) | 0.199 | 0.137 | 0.137 | 0.199 | 0.168 |
| river HST + CADAL | 0.205 | 0.153 | 0.136 | 0.197 | 0.173 |
| PCA + POT, static | 0.274 | 0.072 | 0.072 | 0.274 | 0.173 |
| **PCA + POT + CADAL** | **0.280** | 0.144 | 0.096 | **0.313** | **0.208** |

- **The two components need each other.** PCA is the better detector on undisturbed data
  (+0.075 MCC; +51% PR-AUC on held-out entities, `RESULTS.md`). It is also far more sensitive to
  drift: static PCA collapses after a shift (0.072 vs 0.137, p = 0.015), because it reacts to any
  change in how metrics move together.
- CADAL is what makes it usable under drift.
- River HST barely benefits from CADAL: it is partly blind to out-of-range shifts, so it is less
  hurt by them.
- The combined system beats the shipped one on undisturbed data (p = 0.08) and on real SMD drift
  after deployments (p = 0.019). It ties after an announced shift and is worse after an
  unannounced one (0.096 vs 0.137, not significant).

## 5. Scalability (`outputs/scalability/scalability.json`, `benchmark_scalability.py`)

Measured on the development laptop (i7-1165G7, 4 cores / 8 threads, 16 GB), SMD telemetry,
38 metrics, one `DynamicModelManager` per service.

| measure | result |
|---|---|
| memory per service (PCA + CADAL state) | **34 KB**, flat from 1 to 1,000 services (34 MB per 1,000) |
| memory per model, river HST as shipped | 368 MB (about 10,700x more) |
| one process, 100 services, every service through a quarantine decision | **20,500 events/s**, p50 0.03 ms, p99 0.07 ms per event |
| quarantine decision (fit and test a challenger) | ~42 ms |
| serving blocked by a decision, synchronous / asynchronous | up to 81 ms / **0.4 ms** |
| worst single event while 100 decisions run at once (async) | 148 ms (Python GIL contention; p99 unaffected) |
| horizontal: 200 services over 1 / 2 / 4 worker processes | 35k / 46k / 70k events/s |
| snapshot per registered version | ~5 KB |
| replica picks up a new production version via MLflow | 25 ms median |

Capacity statement.
- **One process:** at a 15-second Prometheus scrape interval, one process at ~20,000 events/s
  can in principle score ~300,000 services per scrape. In practice memory is the bound: about
  34 MB per 1,000 services.
- **Fleet scale:** services are partitioned across ml-backend replicas by a stable hash of
  `service_id`. Per-service state is independent, so throughput grows with replicas
  (sub-linearly on a 4-core laptop).
- **Shared state:** MLflow holds only the small, versioned snapshots.

## 6. Requirements

| | status |
|---|---|
| FR1 automatic drift detection | met (ADWIN on the score stream, Page-Hinkley and KSWIN available) |
| FR2 three triggers | met (drift, scheduled validity check, Kubernetes change events) |
| FR3 rollback within one scoring cycle | met: restoring a version takes milliseconds and asynchronous decisions block serving for ≤ 0.4 ms |
| FR4 every transition logged with context | met (registry transitions with reason and evidence, JSONL and MLflow) |
| FR5 replicas without shared memory | met for the mechanism (25 ms MLflow sync); not load-tested on a real cluster |
| FR6 ≤ 5 ms per event | met (p99 0.07 ms) |
| FR7 F1 ≥ 0.65 | **not met**: the best F1 on SMD is ~0.3; this is the detector's ceiling on unsupervised SMD, not a lifecycle limit |

## 7. How the system got here (what the first evaluation taught)

Each change was found from a measured failure on development data:
1. **Re-baselining instead of retraining.** Promoted challengers fitted on 12 hours forgot weeks of
   normal and caught 24% of the anomalies the static model caught 86% of.
2. **Only a change event licenses retraining.** A day-long incident passed the learnability test
   and the retrained model missed the rest of it (recall 0.87 to 0.08).
3. **Re-baselining is held to the target alarm rate, not the retrain noise floor.** With PCA the
   floor let a 55% alarm rate through.
4. **PCA + smoothing + POT** replaced HST (see `RESULTS.md`).
5. **Lazy trees and asynchronous decisions** made the lifecycle cheap enough to scale.

## 8. Threats to validity

- Injected drift is synthetic (level shifts, clipped to the [0, 1] range of normalised SMD). The
  real-drift evidence is SMD's own train-to-test drift (`noop_deploy`) and NAB.
- One injection seed, no confidence intervals over seeds.
- About 60 paired tests were run with no correction.
- Every design decision was made on the 8 development entities; the held-out columns are the
  claims.
- Single laptop for the scalability numbers; no real multi-node cluster test.
- PCA needs clearly more warm-up samples than metrics (the RCAEval Sock Shop cases show the
  failure mode).
