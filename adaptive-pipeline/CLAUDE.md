# adaptive-pipeline

Component 4 — Adaptive Learning Decision Engine (RL-based), per `docs/README.md`'s component
tech-stack listing (`docs/README.md` line ~130).

**Tech**: Python 3.11 (uv-managed), Stable-Baselines3 (PPO/DQN/A2C), Gymnasium (environment
definition), MLflow (policy versioning), TensorBoard (training visualisation). `docs/README.md`
also lists Ray RLib as a scalable alternative and Optuna for RL hyperparameter search — not
added to `pyproject.toml` yet; add them if/when a single-machine Stable-Baselines3 setup turns
out to be insufficient, rather than pulling in the heavier distributed stack up front.

**Status**: scaffold only. `pyproject.toml` lists the dependency set; `uv sync` has
deliberately **not** been run yet (Stable-Baselines3 pulls in PyTorch, a large download) — that's
the next manual step for whoever starts this component, matching the pattern in
`docs/Doc3_Execution_Guide.md` of manual environment setup before coding tasks. No `src/`
modules exist beyond an empty `__init__.py`.

**Important, unlike `ml-pipeline/`: there is no detailed technical guide for this component.**
`docs/Component_1_2_Technical_Guide.md` gives Component 1-2 a full week-by-week implementation
walkthrough; nothing equivalent exists for Component 4. `docs/Doc1_Technical_Architecture.md`'s
actual component inventory (§2) does not include an RL/adaptive-learning component at all — it
only appears in `docs/README.md`'s draft tech-stack listing, which is otherwise mostly empty
headers ("Objectives", "Research Contributions" are blank). Treat this as a genuinely open
research problem, not an under-documented but otherwise-specified one.

**Before any training code makes sense, these need deciding first** (none of this is decided
yet — don't assume an answer and start coding):
- **State representation**: presumably anomaly scores per service + dependency graph shape from
  `services/decision-engine`, but the exact feature vector isn't defined anywhere.
- **Action space**: presumably maps onto `services/decision-engine`'s `RemediationLevel`
  enum (Watch/Warn/Degrade/Critical) or a more granular action (scale-by-N, traffic-weight-%),
  but this hasn't been decided either.
- **Reward signal**: recovery time, downtime cost, and false-positive cost are all plausible
  candidates per `docs/README.md`'s framing; none chosen.
- **Training data / environment**: `docs/README.md` mentions SimPy for discrete-event
  simulation, implying offline simulation rather than training against live telemetry directly
  — also not decided.
- **Relationship to `services/decision-engine`**: my own inference, not documented anywhere, is
  that this would eventually learn better remediation policies than `PolicyEvaluator`'s fixed
  score thresholds, or tune those thresholds over time. Confirm this before building toward it.

**Suggested first real step**: write up a short problem definition (state/action/reward/
environment choice) as a design doc before writing any Gymnasium environment or training script.
