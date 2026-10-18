# Component 2 demo script: dynamic model updating (Progress Presentation 1)

A live demo of five to seven minutes, run on Shalon's laptop. It shows the anomaly detector
(Component 1) and CADAL dynamic model updating with operator queries (Component 2). Everything on
screen is real: real SMD telemetry replayed through the evaluated lifecycle, persisted to
TimescaleDB and streamed over Redis and a WebSocket.

## Before the panel (10 minutes ahead)

1. Start Docker Desktop, then the database and message bus:
   ```powershell
   docker compose -f infrastructure/local/docker-compose.demo.yml up -d
   ```
2. Start the backend in its own terminal:
   ```powershell
   cd services/ml-backend
   uv run uvicorn app.main:app --port 8000
   ```
3. Start the frontend in a second terminal:
   ```powershell
   cd frontend
   pnpm dev
   ```
   Then open `http://localhost:5173/model-lifecycle`.
4. Check that the header pill says **Live**. Hover it: the tooltip should show TimescaleDB, Redis on,
   and 6 services at 60 events/s.
5. Type your name into the **Operator** box. It is recorded in the audit trail.
6. Click **Reset**, then let it run for about a minute so every chart fills up. All six services
   should be **Stable** (or showing a grey **Validity check**) and below the red dashed line.

Have a terminal ready for step 6 of the demo (the database rows).

## The demo

### 1. What you are looking at (45 s)

Point at the six service cards.
- Each service replays a real SMD server's telemetry: 38 metrics, one sample a minute, replayed
  60 times faster.
- The line is the anomaly score from Component 1: a smoothed PCA reconstruction error.
- The red dashed line is that model version's own alarm threshold, fitted per service by Peaks
  Over Threshold at a 1% risk. That is why a single global cutoff isn't needed.

Point at the four steps in the strip: trigger, quarantine, attribute, act. A model is never
changed on a hunch. When the data shifts, CADAL first collects a day of evidence while the current
model keeps serving. It then works out *why* the data changed, and only then acts.

### 2. A deployment is learned (about 40 s)

Click **Deploy** on **Auth Service**.
- The score jumps above the line: the deployment changed the service's baseline, so the old
  model alarms on everything. That is the failure mode of a static model.
- The pill turns **Quarantine**. In the event feed: "deployment observed", "quarantine opened".
- About 25 s later: **Concept drift → Promote**. The score drops back below the line on a new
  model version.

Say: "Because a deployment event explains the shift, CADAL is allowed to learn it. It tried
re-baselining the shifted metrics first, checked that the repaired model is quiet on held-back
data, and promoted it as a new version."

### 3. The novel part: CADAL asks when it cannot know (about 60 s)

Click **Silent change** on **Inventory Service**. This is the same kind of shift, but with **no
deployment event**.
- Score above the line, then quarantine, as before.
- About 25 s later an operator query card appears at the top: *"Inventory Service: new normal,
  or incident?"*

Read the three evidence lines on the card. The serving model alarms on almost everything, and a
retrained challenger fits the new behaviour, so the shift is learnable. But nothing explains it,
and **without labels a new normal looks exactly like a long incident**. Any fully automatic system
has to guess here. CADAL keeps the current model serving, parks the validated challenger, and asks.

Click **New normal**.
- **Promote**, with "operator shalon confirmed a new normal (query q-…)" in the audit trail.
- The score returns below the line.

Mention the safeguards:
- An unanswered query falls back to hold after about 5 minutes.
- There is one open question per service at a time.
- After an "incident" answer or an expiry, CADAL won't ask again for a day, to avoid alert
  fatigue.

### 4. An incident is never learned (about 40 s)

Click **Incident** on **Payments Service**.
- A short spike above the line: Component 1 detects it.
- A drift quarantine opens. About 25 s later: **No change → Resume** (or **Incident → Hold**).

Say: "This is where the original 'ADWIN fires, roll back' design and blind retraining both go
wrong. A model that adapts to every drift learns the incident as normal and stops detecting it.
CADAL saw that the shift went away, so it kept the model unchanged."

### 5. Rollback and the version history (about 40 s)

Go to **Models**.
- The registry shows each service's serving version, the recent alarm rate against the 1% POT
  target, and how many versions it has.
- Click **Auth Service**: the version history lists warm-up, the re-baselined version and any
  validity checkpoints, each with the reason it was created.
- Click **Roll back last promotion**. The service is back on v1 instantly, and the rollback is
  recorded with your name. Every transition is versioned and reversible.

### 6. It is a real system (about 30 s, optional)

Show the persisted rows:
```powershell
docker exec selfheal-demo-timescaledb-1 psql -U postgres -d selfheal -c "select service_id, trigger, verdict, action, left(reason,60) from lifecycle_decisions where action <> 'resume' order by time desc limit 6"
docker exec selfheal-demo-redis-1 redis-cli XREVRANGE anomaly_events + - COUNT 2
```
The Redis stream is what the Decision Engine (Component 4) will consume.

## If something goes off script

| What happens | What to do or say |
|---|---|
| Header says **Offline** | The backend or Docker isn't running. Restart it; the page reconnects by itself within 30 s. Dashboard and Models fall back to sample data. |
| Deploy on Auth is **held** instead of promoted | "CADAL found the new behaviour still moving and refused to learn a regime that hasn't settled." Then show **Deploy on Orders** or **Inventory**, which promote in every rehearsal. |
| Silent change on Inventory is **promoted** without asking | Re-baselining repaired the shift on its own, and that cheap, reversible repair doesn't need an explanation. Show **Silent change** again after a minute. In rehearsals it asked 4 times out of 5. |
| A query card appears on a service you didn't touch | Real SMD data drifts by itself. That is CADAL working; answer it. |
| Everything is busy and confusing | Click **Reset** and pick one scenario. |

## Numbers to quote (from `ml-pipeline/RESULTS_COMPONENT2.md`)

- After a deployment, CADAL vs a static model: MCC **0.144 vs 0.072** (p = 0.0005, all 28 SMD
  entities). After the shift alone: **0.107 vs −0.001**.
- On SMD's own real drift (`noop_deploy`): **0.313 vs 0.274**, held-out p = 0.026.
- No harm on undisturbed data: **0 losses in 28** entities.
- Operator queries (CADAL-HITL) target the remaining weak spot, silent drift. After the shift,
  false alarms fall from **0.76 to 0.41**, at about two questions per service over 20 days of data.
  Section 9 of the results file has the full trade-off.
- Scalability:
  - **34 KB per service**, flat up to 1,000 services;
  - **20,500 events/s** in one process with 100 services all going through quarantine decisions
    (p99 0.07 ms per event);
  - a decision blocks serving for **0.4 ms** when it runs asynchronously;
  - 70k events/s across 4 worker processes.

Don't quote demo timings as results. The demo runs the evaluated lifecycle, 60 times faster than
real time, on calm replay windows chosen so that each scenario shows up clearly.
