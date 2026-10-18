# Component 2: Dynamic Model Updating with Concept Drift Detection

### Research positioning, design and evaluation of CADAL (Change-Aware Drift Attribution Lifecycle)

Owner: Shalon Anton Fernando (IT22362544), project J26-SE-335. Code: `ml-pipeline/` (see
`ml-pipeline/README.md` "Component 2"). Results: `ml-pipeline/RESULTS_COMPONENT2.md`.

---

## 1. One-paragraph summary

A streaming anomaly detector that sees its score distribution shift cannot tell from that
signal alone *why* it shifted. The service may be failing (an **incident**: keep the model,
keep alerting, learn nothing). It may have legitimately changed, for example after a deployment
(**concept drift**: adopt a model and threshold fitted to the new normal). Or the model itself
may have gone insensitive (**model decay**: roll back to the last good version). These three
causes need opposite responses. The original Component 2 design, "ADWIN fires → roll back to the
last stable snapshot" (Component_1_2_Technical_Guide Part 5, Doc1 §6), is correct only for the
third. It is actively harmful for the motivating example of the proposal itself, because
restoring the pre-deployment model restores the pre-deployment notion of normal. CADAL makes
the lifecycle decision *after* attributing the shift. It uses label-free evidence gathered in a
short quarantine: persistence, a frozen challenger's stationarity test, a support check, and a
prior from Kubernetes change events. It then serves only validated, versioned and audited
model+threshold pairs. It is evaluated against six baselines on all 28 SMD entities under
injected deploy, silent and no-op drift scenarios.

## 2. The gap, stated precisely

| Capability | river | MLflow | METER / ARCUS / AnDri / MemStream | McUDI, Lyu et al. (AIOps maintenance) | FUNNEL / SCWarn / Gandalf / Lumos | Dynatrace / Datadog | Myrtollari et al. 2025 | **CADAL** |
|---|---|---|---|---|---|---|---|---|
| Streaming anomaly detection | ✔ | | ✔ | | | ✔ (closed) | ✔ | ✔ (river HST) |
| Drift detection | ✔ | | ✔ | ✔ | | ? | ✔ | ✔ ADWIN / PH / KSWIN |
| Distinguishes incident vs new normal vs decay before acting | | | partly (in-model) | | | | ? | **✔ explicit verdicts** |
| Uses deployment/change events as evidence for the *detector's* lifecycle | | | | | judge the change, not the detector | manual baseline reset | | **✔** |
| Versioned model + threshold, rollback, audit trail | | ✔ (no trigger) | | | | closed | | **✔ MLflow aliases + JSONL** |
| Label-free validation before promote **and** before rollback | | | | McUDI (degradation only) | | | | **✔** |
| Rollback in one scoring cycle for HST | | | | | | | | **✔ 13 KB sparse snapshots** |
| Asks a human only when label-free attribution cannot decide, with a validated candidate waiting | | | | | | | | **✔ CADAL-HITL** |

Reading of the table, and the claim it supports. Prior work has each piece: river's online
learning and ADWIN, MLflow's registry, adaptive detectors such as METER, ARCUS, AnDri and
MemStream, drift-triggered retraining for supervised AIOps models (Lyu et al., McUDI), and
change-impact assessment (FUNNEL, SCWarn, Gandalf, Lumos). No work we found joins them into
one closed loop that does all of the following:

1. *attributes* a detected shift to incident, concept drift or decay before choosing an action;
2. uses exogenous Kubernetes change events as a prior on that attribution, for the
   anomaly detector's own lifecycle;
3. validates both directions of a model swap without labels (challenger before promote, rollback
   target before rollback);
4. versions the model together with its threshold so that every behavioural change of the
   detector is an auditable transition;
5. asks the operator a single categorical question ("new normal or incident?") only when the
   label-free evidence cannot decide. A validated challenger is kept ready, so the answer takes
   effect immediately and is audited, and an unanswered question falls back safely to hold.

That combination is the contribution. The individual algorithms (ADWIN, HST, percentile
calibration) are deliberately standard and cited.

Honest caveat on novelty. Myrtollari, Andreou, Panagidi and Hadjiefthymiades (IEEE ISORC 2025)
present "an unsupervised concept drift-aware anomaly detection system for microservices
applications on Kubernetes" using Prometheus and optimal stopping theory. It is the closest
prior work, and its full text was not accessible to us (SSRN/IEEE paywall). Before submission,
read it and state the difference explicitly. From its abstract it addresses *when* to retrain
under drift. CADAL addresses *what kind* of drift happened and *which* lifecycle action follows,
and adds change events, verified rollback and the registry and audit layer. If it turns out to
use deployment events or incident-versus-drift attribution, narrow the claim to the
remaining items (verified rollback, model+threshold co-versioning, sparse snapshots, evaluation
protocol).

## 3. Related work (what each line does and does not do)

**Streaming anomaly detection under drift.**
- METER (Zhu et al., PVLDB 17(4), 2024) uses a hypernetwork to adapt a base detector to new
  concepts, with an evidential drift controller. Adaptation happens inside the model. There is no
  exogenous evidence and no versioned rollback.
- ARCUS (Yoon et al., KDD 2022) does adaptive model pooling with drift-aware pool updates for
  autoencoder detectors.
- AnDri (Park, Chiang, Milani, arXiv 2506.15831, 2025) separates sustained pattern shifts
  (drift) from isolated deviations (anomalies) by tracking pattern membership over time. It is
  the closest *algorithmic* idea to our persistence evidence. It uses no exogenous events and
  does no versioning or rollback.
- MemStream (Bhatia et al., WWW 2022) and MIDAS-F gate memory updates on the anomaly score to
  avoid poisoning. **We found empirically (Section 6) that gating on the alarm threshold lets an
  escalating incident creep into "normal", and that any continuously learning HST loses recall
  on SMD's long anomaly segments.** This is a negative result worth reporting.

**Model maintenance in AIOps.**
- Lyu, Li, Jiang and Hassan ("On the Model Update Strategies for Supervised Learning in AIOps
  Solutions", arXiv 2311.03213) find that active update strategies beat stationary models, and
  that drift-guided retraining beats blind periodic retraining. Their setting is supervised
  models with labels at retrain time.
- McUDI (Poenaru-Olaru et al., arXiv 2401.14093, 2024) is an unsupervised degradation
  indicator that decides when an AIOps failure-prediction model needs retraining. It answers
  "when", not "which action". It has no rollback and no change-event prior.

**Change and deployment impact.**
- FUNNEL (Zhang et al.), SCWarn (Zhao et al., ESEC/FSE 2021), Gandalf (Li et al., NSDI 2020) and
  Lumos (KDD 2020) decide whether a *software change* is bad, for the operators.
- CADAL uses the same signal in the other direction: whether the *anomaly detector* should
  accept the post-change behaviour as normal. The two are complementary. The project's Decision
  Engine (teammate component) could consume a CADAL "incident after deployment" verdict as
  evidence for a bad change.

**Commercial practice.** Dynatrace's auto-adaptive baselines can be retrained "based on a
scheduler, a business calendar, or any other trigger, such as successful load tests or software
deployments". Resetting a baseline after an architectural change is a manual action, and the
mechanism is closed. This confirms the practical need. It is not a scientifically comparable
baseline.

**Tools.** Chantilly and Beaver (online-ml ecosystem) deploy and serve river models. They do not
decide lifecycle transitions. MLflow (Zaharia et al., 2018) versions models but has "no automated
trigger" (proposal §2). MLflow 3 also deprecates the registry *stages* the proposal planned to
use; CADAL uses aliases and tags instead.

**Human feedback and active learning under drift.**
- Active learning for drifting streams (Žliobaitė et al., TNNLS 2014) spends a labelling budget on
  *instance labels* to keep a classifier current.
- Opprentice (Liu et al., IMC 2015) and Label-Less (INFOCOM 2019) collect operator anomaly labels
  to configure KPI detectors.
- DREAM uses human feedback to adapt malware classifiers after drift.
- The closest recent work is a self-adaptive anomaly detector for connected vehicles (arXiv
  2607.08373, 2026). It pairs drift detectors with an operator-triggered retraining loop.

In all of these the human supplies labels, or decides *to retrain*. CADAL-HITL instead asks one
question about the *cause* of a shift, and only in the single verdict where unsupervised
attribution is undecidable: persistent, learnable and unexplained. It is evaluated on
label-efficiency (MCC gained per question) and on robustness to wrong answers, not on labelling
cost.

**Evaluation methodology.** Point-adjusted F1 overestimates detectors (Kim et al., AAAI 2022), so
CADAL is evaluated with point-wise F1 plus event-wise recall, and the point-adjusted variant is
not used.

## 4. Design

```
                         ┌──────────── change events (K8s Deployment watch) ───────────┐
                         ▼                                                             │
 telemetry ─► champion HST ─► score ─► alarm (score ≥ version threshold) ─► Redis / dashboard
                 │ (frozen while serving)       │
                 │                              ├─► ADWIN on scores (drift trigger, up / down)
                 │                              └─► scheduled validity check (time trigger)
                 ▼
          QUARANTINE (alerting continues, buffer N events: 720 if a change explains it, else 1440)
                 │
                 ├─ champion tail alarm rate      (persistence: did the shift last?)
                 ├─ challenger fit → calib → tail (frozen stationarity test: is it learnable?)
                 ├─ tail out-of-support rate      (is a feature still moving away?)
                 ├─ change event in horizon       (prior: lowers the persistence required)
                 └─ shift direction               (down + alarm collapse → decay)
                 ▼
          attribute() ─► INCIDENT → HOLD      champion restored exactly
                       ─► CONCEPT_DRIFT → PROMOTE   challenger + its own threshold, new version
                       ─► MODEL_DECAY → ROLLBACK    only if the target fits recent data
                       ─► NO_CHANGE → RESUME
                 ▼
          MLflow registry: version, `production` alias, archived tags, transition JSON + JSONL audit
```

Key design decisions, each motivated by a measured failure (Section 6 has the evidence):

1. **Attribute before you adapt** (`src/drift_attribution.py`). These are pure, unit-tested
   rules. Every threshold is a multiple of the target alarm rate r0 (3% at the 97th
   percentile), so the rules transfer across entities with different score scales
   (`ml-pipeline/RESULTS.md` showed absolute thresholds do not). The learnability line adds
   a one-sided 99% binomial slack for the tail size.
2. **Frozen serving, versioned change.** The served model does not learn between versions.
   Continuous learning (river's default, Doc1's "online learning first" principle) cost recall
   on SMD in every variant tried, because HST's sliding reference window absorbs long anomaly
   segments. The detector changes only through transitions that are attributed, validated and
   registered.
3. **Calibrate the way you serve.** Each version carries its own threshold. Frozen models are
   calibrated on frozen held-out scores; learning variants are calibrated prequentially
   (score, then learn). Calibrating a learning model on frozen scores left promoted
   challengers silent.
4. **Validate both directions.** A challenger is promoted only if it finds the buffer's tail
   normal (stationarity). A rollback target is restored only if it still discriminates on
   recent data. This prevents the ping-pong of restoring a pre-deployment model onto the
   post-deployment normal.
5. **Change-aware evidence.** A Kubernetes rollout (`src/change_events.py`) opens a quarantine
   immediately (event trigger) and halves the persistence required (720 vs 1440 events). A change
   during an open quarantine restarts it, because evidence about the post-change regime must come
   from after the change.
6. **Structure-sharing sparse snapshots** (`src/hst_state.py`). The structure of a river HST is a
   pure function of (seed, config, feature names). Only per-node masses are learned, and only a
   few thousand of ~1.6M nodes carry mass. Snapshots are ~13 KB instead of a 71 MB pickle,
   capture takes ~27 ms and restore ~37 ms instead of ~3.7 s and ~5.9 s, and challengers reuse
   the champion's structure (reset takes ~4 ms) instead of rebuilding it (~16 s). This is what
   makes proposal FR3 (rollback within one scoring cycle) achievable at all.
7. **Repair by re-baselining before retraining** (added after the first evaluation). When the
   level of some metrics moved, the champion is kept and only those metrics are shifted back onto
   its baseline, using robust medians. This is preferred over a challenger fitted on one day,
   which forgets weeks of normal variation; on SMD such challengers caught 24% of the anomalies the
   static model caught 86% of. Re-baselining is held to the target alarm rate.
8. **Only a change event licenses replacing the model.** Without a deployment or configuration
   event, a persistent shift that only a retrained model explains is held as a probable incident.
   On SMD a day-long incident passed the learnability test and retraining on it silenced the
   detector for the rest of the incident.
9. **Asynchronous decisions.** A closed quarantine is evaluated on a copy of the champion in a
   background thread while the champion keeps scoring; the swap blocks serving for ≤ 0.4 ms.
10. **Component 1 v3** (`src/detectors.py`, `src/lazy_hst.py`):
    - PCA reconstruction error with EWMA smoothing and Peaks-Over-Threshold calibration replaces
      Half-Space Trees as the default detector (held-out PR-AUC +51%, `ml-pipeline/RESULTS.md`).
    - Lazily built trees keep HST available at ~0.1 MB instead of ~370 MB per model.
    - Memory per monitored service is 34 KB.
11. **Operator in the loop (CADAL-HITL).** The "learnable but unexplained" case gets the verdict
    `ambiguous` and the action `ask`, instead of being held as a probable incident:
    - The champion keeps serving and the validated challenger is parked as a pending candidate.
    - The answer "new_normal" promotes that candidate, and the query id and operator are recorded
      on the version and the transition. The answer "incident" holds and pauses asking.
    - Safeguards: a query TTL with a fallback to hold, one open query per service, a budget per
      day, and a cooldown after an "incident" answer or an expiry.
    - It is exposed in `services/ml-backend` as `POST /api/queries/{id}/answer` and on the
      dashboard's Model lifecycle page.

## 5. Mapping to the proposal's requirements

| Req | Status | Where / evidence |
|---|---|---|
| FR1 automatic drift detection | Met | `ScoreDriftMonitor` (ADWIN δ=0.002 default, Page-Hinkley, KSWIN) |
| FR2 three simultaneous triggers | Met | drift (ADWIN), time (`scheduled_every`), event (`ChangeEvent`, K8s watcher) |
| FR3 rollback within one scoring cycle | Met | restoring a version takes milliseconds; asynchronous decisions block serving for ≤ 0.4 ms (was up to 8.7 s before `async_decisions`) |
| FR4 every transition logged with context | Met | `TransitionRecord` (step, wall time, reason, evidence) → JSONL + MLflow `transitions/*.json` |
| FR5 multi-replica without shared memory | Met (mechanism) | `MLflowRegistry.sync_production()` + `materialize/apply`; not load-tested across real replicas |
| FR6 ≤ 5 ms added per-event latency | Met | p99 0.07 ms per event with 100 services in one process (`benchmark_scalability.py`) |
| FR7 F1 ≥ 0.65 throughout | **Not achievable as stated** | Component 1's HST tops out at F1 0.38 to 0.57 on its best entity *before* any drift (`ml-pipeline/RESULTS.md`). Lifecycle management cannot exceed the detector's ceiling. Restate it as a relative goal (dynamic ≥ static, and recovery after drift). |
| NAB | Evaluated | 46 real NAB series, `evaluate_nab_dynamic.py`; the simplified NAB-style score is reported, but MCC is the primary metric (`ml-pipeline/RESULTS_COMPONENT2.md` §3) |

## 6. Results

Full tables: `ml-pipeline/RESULTS_COMPONENT2.md`; the panel-facing summary is
`docs/Component_2_Panel_Response.md`. The first evaluation found CADAL did not beat a static
model. Diagnosing why produced design items 7 to 10. The final configuration, judged on 20
held-out SMD entities (MCC, CADAL vs static, same detector):

- **No harm:** with no injected change CADAL is never worse (0 of 28 entities).
- **After a deployment that shifts the baseline:** 0.128 vs 0.074 (p = 0.016). Post-shift
  0.091 vs 0.000, because the static model alarms on 99.5% of normal time.
- **On SMD's real train-to-test drift**, with a deployment event allowing a model update:
  0.297 vs 0.243 (p = 0.026).
- **After an unannounced shift:** not significant for plain CADAL. This was the main
  limitation, and CADAL-HITL targets it.
- **CADAL-HITL** (operator queries, simulated from labels; `RESULTS_COMPONENT2.md` §9):
  - After an unannounced shift, false alarms fall from 0.76 to 0.41 (p < 0.0001) and post-shift
    MCC rises from 0.031 to 0.083 (p = 0.008), all 28 entities.
  - It asks about 1.5 questions per service per 20 days, and is unaffected by 20% wrong answers.
  - It costs a little, not significantly, on undisturbed data and on real SMD drift. A confirmed
    new normal still promotes a challenger fitted on one day, and that challenger may generalise
    worse.
- **Against other policies:** the original "roll back on drift" design never beats static, and
  blind periodic retraining loses 40% of the MCC when nothing changes. CADAL has the best mean
  over all scenarios.
- **NAB** (46 real series): small, non-significant gain.
- **RCAEval:** the improved detector catches all Online Boutique faults with MCC 0.700 vs 0.368.

## 7. Threats to validity (put these in the paper)

- **Injected drift.** SMD has no deployment log, so benign drift is synthetic (level shifts of
  +0.2 to 0.3 on 30% of features). Real deployments also change correlations and variance.
  Mitigation: also report the "none" scenario (natural SMD drift only) and the no-op deployment
  scenario.
- **Development entities.** Every design choice was made on the 8 `machine-1-*` entities; the
  claims are the 20 held-out entities, NAB and RCAEval.
- **Detector dependence.** The lifecycle was evaluated with two detectors: PCA as the default, and
  river HST as shipped. CADAL helps PCA much more than HST, because PCA is far more
  drift-sensitive. The "continuous learning hurts" finding was measured with HST (window-based
  mass); PCA does not learn continuously at all.
- **Multiple comparisons.** About 60 paired tests were run without correction.
- **Inherent ambiguity.** An incident that settles into a steady, self-consistent state for longer
  than the quarantine is indistinguishable from a new normal without labels. The change prior
  and longer silent quarantine reduce this risk but cannot remove it.
- **Closest prior work unread** (Myrtollari et al. 2025), see Section 2.

## 8. Where this could be published

Software-engineering and AIOps venues fit the contribution (a lifecycle framework plus an
empirical study with negative results) better than core ML venues:

- ICSE-SEIP, ESEC/FSE Industry, ASE (NIER or tool track)
- IEEE ICSA
- ISSRE, or the AIOps workshop at ICSE/ASPLOS
- Journal of Systems and Software / Empirical Software Engineering, for an extended version

The negative findings (unconditional rollback is harmful, continuous HST learning loses recall,
alarm-gated learning is poisonable, frozen calibration of learning models silences them) are
publishable on their own as an "experience report".

## References

1. A. Bifet, R. Gavaldà. Learning from Time-Changing Data with Adaptive Windowing. SDM 2007.
2. S. C. Tan, K. M. Ting, T. F. Liu. Fast Anomaly Detection for Streaming Data. IJCAI 2011.
3. J. Montiel et al. River: Machine Learning for Streaming Data in Python. JMLR 22(110), 2021.
4. M. Zaharia et al. Accelerating the Machine Learning Lifecycle with MLflow. IEEE Data Eng. Bull. 41(4), 2018.
5. Y. Su et al. Robust Anomaly Detection for Multivariate Time Series through Stochastic RNN (OmniAnomaly, SMD). KDD 2019.
6. J. Zhu, S. Cai, F. Deng, B. C. Ooi, W. Zhang. METER: A Dynamic Concept Adaptation Framework for Online Anomaly Detection. PVLDB 17(4):794-807, 2024. https://www.vldb.org/pvldb/vol17/p794-zhu.pdf
7. S. Yoon, Y. Lee, J.-G. Lee, B. S. Lee. Adaptive Model Pooling for Online Deep Anomaly Detection from a Complex Evolving Data Stream (ARCUS). KDD 2022. https://arxiv.org/abs/2206.04792
8. J. Park, F. Chiang, M. Milani. Adaptive Anomaly Detection in the Presence of Concept Drift (AnDri). arXiv 2506.15831, 2025. https://arxiv.org/abs/2506.15831
9. S. Bhatia et al. MemStream: Memory-Based Streaming Anomaly Detection. WWW 2022. https://arxiv.org/abs/2106.03837
10. Y. Lyu, H. Li, Z. M. Jiang, A. E. Hassan. On the Model Update Strategies for Supervised Learning in AIOps Solutions. arXiv 2311.03213. https://arxiv.org/abs/2311.03213
11. L. Poenaru-Olaru, L. Cruz, J. Rellermeyer, A. van Deursen. McUDI: Model-Centric Unsupervised Degradation Indicator for Failure Prediction AIOps Solutions. arXiv 2401.14093, 2024. https://arxiv.org/abs/2401.14093
12. N. Zhao et al. Identifying Bad Software Changes via Multimodal Anomaly Detection for Online Service Systems (SCWarn). ESEC/FSE 2021.
13. Z. Li et al. Gandalf: An Intelligent, End-To-End Analytics Service for Safe Deployment in Cloud-Scale Infrastructure. NSDI 2020.
14. J. Lu et al. Lumos: A Library for Diagnosing Metric Regressions in Web-Scale Applications. KDD 2020. https://arxiv.org/abs/2006.12793
15. K. Myrtollari, C. Andreou, K. Panagidi, S. Hadjiefthymiades. An unsupervised concept drift-aware anomaly detection system for microservices applications on Kubernetes. IEEE ISORC 2025. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6367394
16. S. Kim et al. Towards a Rigorous Evaluation of Time-Series Anomaly Detection. AAAI 2022. https://ojs.aaai.org/index.php/AAAI/article/view/20680
17. N. Goix. How to Evaluate the Quality of Unsupervised Anomaly Detection Algorithms? arXiv 1607.01152, 2016.
18. J. Gama et al. A Survey on Concept Drift Adaptation. ACM CSUR 46(4), 2014.
19. Dynatrace documentation: auto-adaptive baselines and baseline reset. https://www.dynatrace.com/news/blog/dynatrace-innovates-again-with-the-release-of-topology-driven-auto-adaptive-metric-baselines/
20. I. Žliobaitė, A. Bifet, B. Pfahringer, G. Holmes. Active Learning With Drifting Streaming Data. IEEE TNNLS 25(1):27-39, 2014.
21. D. Liu et al. Opprentice: Towards Practical and Automatic Anomaly Detection Through Machine Learning. IMC 2015.
22. Self-Adaptive Anomaly Detection with Reinforcement Learning and Human Feedback in Connected Vehicles. arXiv 2607.08373, 2026. https://arxiv.org/abs/2607.08373
