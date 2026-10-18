# Component 2: Response to Panel SE-P03 comments

**Project:** J26-SE-335, Self-Healing AI-Driven Failure Prediction and Automated Recovery
Framework for Microservices
**Component:** Dynamic Model Updating with Concept Drift Detection
**Student:** Shalon Anton Fernando (IT22362544)

The panel asked two things of this component:

1. *State the scalability of your project as well.*
2. *Think about how you will evaluate whether dynamic model updating actually improves failure
   prediction compared with a static model.*

Both are answered below with measured results. Code, data files and full tables:
- code: `ml-pipeline/`;
- detailed numbers: `ml-pipeline/RESULTS_COMPONENT2.md` and `ml-pipeline/RESULTS.md`;
- raw result files: `ml-pipeline/outputs/`.

---

## Comment 1: Scalability

### How the component scales

Each monitored microservice gets its own small, independent model and lifecycle state, so the
system scales out by adding processes:

- **Inside one process:** many services share one Python process. A model per service is a PCA
  detector (a 38 x k matrix) plus its lifecycle state.
- **Across processes and replicas:** services are partitioned across ml-backend replicas by a
  stable hash of `service_id`. Telemetry reaches the right replica through Redis Streams consumer
  groups (Doc1 §3). No replica shares in-memory state with another.
- **Shared state:** only the MLflow model registry is shared. It stores a ~5 KB snapshot per
  model version, so a new replica, or one taking over a service, loads the current production
  version in milliseconds.

Two redesigns made this possible:
- The original Half-Space Trees model used 368 MB of memory per service and took ~100 s to train.
- Model updates used to block scoring for seconds while a replacement model was trained.

### Measured (laptop: Intel i7-1165G7, 4 cores, 16 GB; real SMD telemetry with 38 metrics)

| what | result |
|---|---|
| memory per monitored service | **34 KB** (was 368 MB per service with the original detector) |
| memory for 1,000 services | ~34 MB (flat per-service cost measured from 1 to 1,000 services) |
| scoring throughput, one process, 100 services | **~20,500 events/s**, while every service also went through a full drift decision |
| per-event latency | p50 0.03 ms, p99 0.07 ms (requirement FR6: ≤ 5 ms) |
| one model-update decision | ~42 ms, run in the background |
| scoring blocked by a model update | **≤ 0.4 ms** (was up to 8.7 s in the first design) |
| scale-out, 200 services | 1 process 35k, 2 processes 46k, 4 processes 70k events/s |
| model version size / replica sync | ~5 KB / 25 ms through MLflow |

### Capacity statement

- With Prometheus scraping every 15 s, a service produces 4 events per minute.
  - At ~20,000 events/s, one process can score about **300,000 services per scrape interval**.
  - In practice memory is the binding resource: ~34 MB per 1,000 services.
- A single ml-backend replica therefore handles thousands of services. Larger fleets are handled
  by adding replicas: throughput grows with the number of replicas, with no shared memory.

### Limits

- Measured on one laptop. Multi-node behaviour is designed but has not been load-tested on a real
  cluster.
- When very many services make a model-update decision at the same instant, Python's global
  interpreter lock makes individual events wait. The worst single event was 148 ms with 100
  simultaneous decisions; p99 latency was unaffected.

---

## Comment 2: Does dynamic model updating improve failure prediction over a static model?

### Evaluation design

The question is answered with a controlled, paired comparison. The same detector is run on the
same data twice: frozen after training (**static**) and with dynamic updating (**CADAL**, plus
other updating policies for reference).

- **Fair:** both use the same detector and the same per-service threshold calibration. Labels
  are never seen by the updating logic; they are only used afterwards to score the alarms.
- **Not tuned on the test data:** every design decision was made on 8 development machines. All
  claims are checked on **20 held-out machines** and on two other public datasets.
- **Metrics that cannot be gamed:**
  - F1 rewards a stale model that simply alarms on everything when anomalies are common.
  - The primary metric is therefore **MCC**, which scores 0 for any constant alarm.
  - Informedness (recall minus false-alarm rate) is reported alongside.
- **Statistics:** paired Wilcoxon signed-rank tests over machines, with wins, ties and losses
  reported.
- **Drift scenarios:** what static models fail at is change, so the same data is tested
  - unchanged,
  - after a deployment that shifts the service's baseline,
  - after the same shift with no deployment signal,
  - after a deployment that changes nothing.

### Data (all public, real telemetry)

| dataset | what it is | used for |
|---|---|---|
| SMD (Su et al., KDD 2019) | 28 production servers, 38 metrics, 1-minute samples, labelled anomalies | main comparison; its test half also drifts naturally from the training half |
| NAB (Numenta) | 46 real cloud, traffic and social metric series with labelled anomaly windows and real regime changes | real-drift check on other data |
| RCAEval RE1 (Pham et al., 2025) | 250 real fault injections (CPU, memory, disk, network delay and loss) in Online Boutique and Sock Shop on Kubernetes | failure-detection accuracy on real microservices |

### Results

**Dynamic vs static, same detector (SMD, MCC):**

| situation | all 28 machines | 20 held-out machines |
|---|---|---|
| no injected change | 0.280 vs 0.274: never worse (0 of 28 worse) | 0.250 vs 0.243: never worse |
| after a deployment that shifts the baseline | **0.144 vs 0.072** (22 better, 5 worse, p = 0.0005) | **0.128 vs 0.074** (p = 0.016) |
| only the period after the shift | **0.107 vs −0.001** (p < 0.0001) | **0.091 vs 0.000** (p = 0.002) |
| real SMD drift, model update allowed by a deployment | **0.313 vs 0.274** (p = 0.049) | **0.297 vs 0.243** (p = 0.026) |
| shift with no deployment signal | 0.096 vs 0.072 (not significant) | 0.078 vs 0.074 (not significant) |

**What this shows:**
- After a change, a static model is useless. It alarmed on 99.5% of normal time, so its MCC is
  0. Dynamic updating restores a working detector and cuts those false alarms to 39%.
- On SMD's own real drift, dynamic updating predicts failures significantly better than the
  static model, on machines it was not designed on.
- When nothing changes, dynamic updating never made a machine worse.

**Against other ways of updating a model (SMD, MCC averaged over the four situations):**

| static | original design (roll back on drift) | blind retraining every 2 days | **CADAL** |
|---|---|---|---|
| 0.173 | 0.173 | 0.158 | **0.208** |

The originally proposed design, "roll back when drift is detected", never improved on static.
Blind periodic retraining helps after a change but costs 40% of the accuracy when nothing
changed. CADAL is the only policy that helps after changes without hurting the rest.

**Real data beyond SMD:**
- **NAB:** dynamic updating MCC 0.106 vs static 0.096 (21 series better, 15 worse, not
  significant). A variant allowed to retrain without a deployment signal reached 0.131 (p = 0.06).
- **RCAEval, real microservice failures:** the improved detector catches **100%** of 125 injected
  Online Boutique faults with a 2-second median delay. Its MCC is 0.700, against 0.368 for the
  original detector (better in 96 of 125 cases).

### Where dynamic updating does not (yet) help

- **Unannounced changes:** a baseline shift with no deployment or configuration event is only
  partly repaired (not significant). This is deliberate. Without such a signal, a persistent
  change cannot be told apart from a long incident without labels, and the system refuses to
  "learn" a possible incident.
- **The accuracy ceiling:** absolute scores stay modest (best F1 ~0.3 on SMD). That is the
  ceiling of unsupervised detection on this dataset, so the proposal's F1 ≥ 0.65 target is not
  reachable.
- **Synthetic deployments:** the injected deployments are level shifts. Real deployments also
  change variance and correlations; SMD's real drift and NAB are the partial check on that.

---

## Summary

| panel comment | answer |
|---|---|
| Scalability | 34 KB and ~0.03 ms per service per event. ~20k events/s per process, 70k with 4 processes. Model updates block scoring for ≤ 0.4 ms. Replicas share only ~5 KB model versions in MLflow. |
| Dynamic vs static | A paired, held-out comparison on real telemetry under controlled drift. Dynamic updating never hurt when nothing changed, restored detection after deployments (MCC 0.128 vs 0.074 on held-out machines), and beat the static model on SMD's real drift (0.297 vs 0.243, p = 0.026). It does not yet fix changes that come without a deployment signal. |
