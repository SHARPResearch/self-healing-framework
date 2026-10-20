# Component 2 demo script: dynamic model updating (Progress Presentation 1)

A live demo of about six minutes, run on Shalon's laptop, plus time for questions. It shows the
anomaly detector (Component 1) and CADAL dynamic model updating with operator queries (Component 2).
Everything on screen is real: real SMD telemetry replayed through the evaluated lifecycle, persisted to
TimescaleDB and streamed over Redis and a WebSocket. Only the three injections (deploy, silent
change, incident) are synthetic, and the script says so.

## Before the panel (15 minutes ahead)

1. Start Docker Desktop and wait until it says the engine is running. Then, from the repo root:
   ```powershell
   docker compose -f infrastructure/local/docker-compose.demo.yml up -d
   ```
2. Backend, in its own terminal:
   ```powershell
   cd services/ml-backend
   uv run uvicorn app.main:app --port 8002
   ```
3. Frontend, in a second terminal:
   ```powershell
   cd frontend
   pnpm dev
   ```
4. Check everything and reset the demo, in a third terminal:
   ```powershell
   cd services/ml-backend
   uv run python scripts/demo_preflight.py --reset
   ```
   It must end with "All checks passed". It checks the database, Redis, the replay speed (60
   events/s), that the container logs are flowing, that the Vite proxy works, and that the three
   services you inject into are calm. Fix anything it flags before going on.
5. Open `http://localhost:5173/model-lifecycle`. The header pill must say **Live**.
6. Type your name into the **Operator** box. It is recorded in the audit trail.
7. Let it run for a minute after the reset so the charts fill. Don't click anything until you start.

Keep the preflight terminal open: if anything looks odd on stage, run it again (without
`--reset`) to see what changed.

Don't leave the stack running for days. The database keeps 6 hours of metrics and 7 days of logs,
but the model versions in the backend's memory grow with every validity check. Restart the backend
and run the preflight with `--reset` before every presentation.

## Who plays what

| Service | Replays | Use it for |
|---|---|---|
| **Orders** | machine-3-10 | **Deploy** (promotes every time in rehearsal) |
| **Inventory** | machine-1-2 | **Silent** (the operator question, every time) |
| **Payments** | machine-1-2, later rows | **Incident** |
| Auth, Shipping, Search | machine-3-8, 3-10 | Don't touch. They run their own drift checks every few minutes, which is realistic background. CADAL decides "no change" on them. |

Orders, Inventory and Payments were chosen by measuring how often each machine's data triggers a
drift check on its own. The other three trigger one about every three minutes. Two of the cards
replay different days of the same machine, so the card shows the row where its window starts.

## The demo

### 1. What you are looking at (45 s)

Point at the six service cards.
- Each service replays a real SMD server's telemetry: 38 metrics, one sample a minute, replayed
  60 times faster. A full lifecycle "day" (1440 events) takes 24 s on stage.
- The line is the anomaly score from Component 1: a smoothed PCA reconstruction error.
- The red dashed line is that model version's own alarm threshold, fitted per service by Peaks
  Over Threshold at a 1% risk. That is why a single global cutoff isn't needed.

Point at the four steps in the strip: trigger, quarantine, attribute, act. A model is never
changed on a hunch. When the data shifts, CADAL first collects a day of evidence while the current
model keeps serving. It then works out *why* the data changed, and only then acts.

Say that the three buttons on each card inject synthetic problems into the real telemetry, so you
can show each kind of cause on demand.

### 2. A deployment is learned (about 40 s)

Click **Deploy** on **Orders Service**.
- The score jumps above the line: the deployment changed the service's baseline, so the old model
  alarms on everything. That is the failure mode of a static model.
- The pill turns **Quarantine**. In the event feed: "deployment observed", "quarantine opened".
- About 24 s later: **Concept drift → Promote**. The score drops back below the line on a new
  model version.

Say: "Because a deployment event explains the shift, CADAL is allowed to learn it. It tried
re-baselining the shifted metrics first, checked that the repaired model is quiet on held-back
data, and promoted it as a new version."

### 3. The novel part: CADAL asks when it cannot know (about 60 s)

Click **Silent** on **Inventory Service**. This is the same kind of shift, but with **no deployment
event**.
- Score above the line, then quarantine, as before.
- About 29 s later an operator query card appears at the top: *"Inventory Service: new normal, or
  incident?"*

Read the three evidence lines on the card. The serving model alarms on almost everything, and a
retrained challenger fits the new behaviour, so the shift is learnable. But nothing explains it,
and **without labels a new normal looks exactly like a long incident**. Any fully automatic system
has to guess here. CADAL keeps the current model serving, parks the validated challenger, and asks.

Click **New normal**.
- **Promote**, with "operator <your name> confirmed a new normal (query q-…)" in the audit trail.
- The score returns below the line.

Mention the safeguards:
- An unanswered query falls back to hold after about 5 minutes.
- There is one open question per service at a time.
- After an "incident" answer or an expiry, CADAL won't ask again for a day, to avoid alert
  fatigue.

### 4. An incident is not learned (about 45 s)

Click **Incident** on **Payments Service**.
- A 12 s spike above the line: Component 1 alarms, so the on-call engineer is paged.
- A drift quarantine usually opens within a few seconds. About 26 s later: **No change → Resume**
  ("shift did not persist, champion still fits"). The model version doesn't change.
- If no quarantine opens (it happens when the service just finished a scheduled check), click
  **Check** on the same card. That is the operator asking "is my model still right?", and you get
  the same verdict about 26 s later.

Say: "This is where the original 'ADWIN fires, roll back' design and blind retraining both go
wrong. A model that adapts to every drift learns the incident as normal and stops detecting it.
CADAL waited, saw that the shift went away, and kept the model."

### 5. One place for everything it did: Logs (about 45 s)

Open **Logs** in the sidebar.
- The strip at the top counts lines per minute by level; the table is a live stream.
- Type `service:service-c-inventory` (or click the **service-c-inventory** chip). You see the whole
  story of step 3 as log lines: injection, alarm raised, quarantine opened, the decision to ask,
  the operator's answer, the model transition.
- Click **Warnings** to see only what needed attention.
- Click **TimescaleDB** or **Redis**: those are the real container logs of the database and
  message bus, in the same stream. One place for the platform and the model lifecycle.

Say: "Every line is also stored in TimescaleDB, so this is the audit trail, searchable after the
fact. Press `/` to jump to the filter, and the download button exports what you're looking at."

### 6. Rollback and the version history (about 40 s)

Go to **Models**.
- The registry shows each service's serving version, the recent alarm rate against the 1% POT
  target, and how many versions it has. Version numbers also include a validity checkpoint
  about every 48 s, so they advance on their own.
- Click **Orders Service**: the version history lists the warm-up model, checkpoints and the
  re-baselined version from step 2, each with the reason it was created.
- Click **Roll back last promotion**. The service is back on the model it had before the
  deployment, and the rollback is recorded with your name. Every transition is versioned and
  reversible.

### 7. It is a real system (optional, about 30 s)

On **Dashboard**, the stat cards, the fleet score trend and the "Lifecycle decisions" chart are
live. Then show the persisted rows:
```powershell
docker exec selfheal-demo-timescaledb-1 psql -U postgres -d selfheal -c "select service_id, trigger, verdict, action, left(reason,60) from lifecycle_decisions where action <> 'resume' order by time desc limit 6"
docker exec selfheal-demo-redis-1 redis-cli XREVRANGE anomaly_events + - COUNT 2
```
The Redis stream is what the Decision Engine (Component 4) will consume.

## Questions to expect

| Question | Answer |
|---|---|
| Is the data real? | The telemetry is the public SMD server dataset (28 machines, 38 metrics, one sample a minute), replayed 60x faster through the same lifecycle that was evaluated. The three injections are synthetic. |
| Why replay instead of live Kubernetes? | The live path is Phase 3 of the plan; the lifecycle code is the same. A replay lets us show a day of lifecycle in 24 s. |
| What if the operator answers wrong? | We simulated 20% wrong answers. Nothing changed significantly (silent-drift MCC 0.109 vs 0.118, p = 0.11). Every promotion is validated, versioned and reversible with one click. |
| Isn't asking the operator a cop-out? | It happens in exactly one verdict: persistent, learnable and unexplained. About 1.5 questions per service per 20 days. An unanswered question falls back to hold. |
| What if an incident lasts a whole day? | That is the limitation. Without labels it looks like a new normal, and the cheap re-baselining repair can absorb it. We saw this in rehearsal: a 25 s incident followed by a validity check was promoted on two of three services. The defences are the validation gate, the audit trail and one-click rollback, and the operator question for the unexplained case. It is listed under threats to validity. |
| Why not just retrain on a schedule? | We tested it: blind periodic retraining loses about 40% of the MCC when nothing changed (0.169 vs 0.280). |
| What about the F1 ≥ 0.65 target? | Not met, and we say so. The best F1 on SMD is about 0.3 for any unsupervised detector. The goal is restated as relative: dynamic ≥ static, and recovery after drift. |
| Why PCA instead of HST? | Held-out PR-AUC +51% and about 10,700 times less memory per model. |
| How does it scale? | 34 KB per service, 20,500 events/s in one process, and a model swap blocks scoring for 0.4 ms. |

## If something goes off script

| What happens | What to do or say |
|---|---|
| Header says **Offline** | The backend or Docker isn't running. Restart the backend (and Docker if needed); the page reconnects by itself within 30 s. Dashboard falls back to the decision engine view, which is empty without it. The lifecycle and Logs pages wait for the backend. |
| Deploy on Orders is **held** instead of promoted | "CADAL found the new behaviour still moving and refused to learn a regime that hasn't settled." Then click **Deploy** on Inventory, which also promotes in every rehearsal. |
| Silent on Inventory is **promoted** without asking | Re-baselining repaired the shift on its own, and that cheap, reversible repair doesn't need an explanation. Click **Silent** on Inventory again after a minute. |
| A query card appears on a service you didn't touch | Real SMD data drifts by itself. That is CADAL working; answer it. |
| Nothing happens after **Incident** | Click **Check** on that card (step 4). |
| A banner says "Model drift detected in Auth, Shipping…" | Those three run their own drift checks. Say they are the background fleet and CADAL will decide "no change" on them. |
| Everything is busy and confusing | Run `uv run python scripts/demo_preflight.py --reset` and pick one scenario. |

## Numbers to quote (from `ml-pipeline/RESULTS_COMPONENT2.md`)

- After a deployment, CADAL vs a static model: MCC **0.144 vs 0.072** (p = 0.0005, all 28 SMD
  entities). After the shift alone: **0.107 vs −0.001**.
- On SMD's own real drift (`noop_deploy`): **0.313 vs 0.274**, held-out p = 0.026.
- No harm on undisturbed data: **0 losses in 28** entities.
- Operator queries (CADAL-HITL) target the remaining weak spot, silent drift. After the shift,
  false alarms fall from **0.76 to 0.41**, at about 1.5 questions per service over 20 days of data.
  Section 9 of the results file has the full trade-off, including what it costs on undisturbed data
  (not significant).
- Scalability:
  - **34 KB per service**, flat up to 1,000 services;
  - **20,500 events/s** in one process with 100 services all going through quarantine decisions
    (p99 0.07 ms per event);
  - a decision blocks serving for **0.4 ms** when it runs asynchronously;
  - 70k events/s across 4 worker processes.

Don't quote demo timings as results. The demo runs the evaluated lifecycle, 60 times faster than
real time, on replay windows chosen so that each scenario shows up clearly.
