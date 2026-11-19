# frontend

SHARP — React 18 + Vite + TypeScript + Tailwind v4 + shadcn/ui observability dashboard
(Doc1 §2 "Observability Dashboard"). Feature-based folder architecture, a deliberate
deviation from Doc2.

The decision-engine work (pipeline visualisation, validation, guardrails, escalation,
execution) is documented in **[`docs/Decision_Engine_Frontend_Guide.md`](../docs/Decision_Engine_Frontend_Guide.md)**.

## Quick start

```bash
pnpm install
pnpm dev      # http://localhost:5173
pnpm build    # typecheck + production build
```

## Routes

| Route | What it is | Data |
|---|---|---|
| `/` | Public marketing landing page (outside the app shell) | static |
| `/login`, `/signup`, `/forgot-password` | Auth UI — mock only, submitting goes to `/dashboard` | none |
| `/dashboard` | Stat cards, recovery-action and anomaly-score charts, service health, incident feed | ml-backend (WebSocket) |
| `/services` | Service table with a detail panel and mock remediation actions | ml-backend |
| `/dependency-graph` | `d3-force` graph, click a node to filter incidents | decision-engine `/api/graph` |
| `/anomalies` | Anomaly list with evidence bundles (`?service=`, `?focus=`) | decision-engine |
| `/decisions` | Decision log table; opens the run modal on click | decision-engine |
| `/decisions/:decisionId` | **Decision run** — full pipeline graph with per-stage state, durations, notifications | decision-engine |
| `/escalations` | Human-in-the-loop queue; approve/reject, 3-attempt delivery timeline | decision-engine |
| `/shadow` | Shadow-mode counterfactual records and metrics | decision-engine |
| `/executions` | Execution log plus guardrail-block evidence | decision-engine |
| `/rules`, `/rules/:id` | Hybrid rule management, validation, audit trail | decision-engine |
| `/incidents` | Incident report, trend chart, reliability metrics, `?filter=` support | mock |
| `/models` | MLflow run registry with params, metrics and a detail dialog | mock |
| `/model-lifecycle` | CADAL lifecycle replay — quarantine, verdict, operator queries | ml-backend (WebSocket) |
| `/logs` | Log explorer | mock |
| `/copilot` | Chat composer with a command palette | llm-copilot |
| `/post-mortems` | Generated post-mortem reports | llm-copilot |
| `/notifications` | Full notification history with filters (also a header popover) | decision-engine |
| `/settings` | Thresholds, model, integrations, notifications, security; runtime engine settings | decision-engine |
| `/profile` | Account details and mock API tokens | mock |

### Which backend

- **decision-engine** — `VITE_API_BASE`, default `http://localhost:8000`. Called
  directly (CORS is open), not through the Vite proxy.
- **ml-backend** — reached through the `/api` and `/ws` proxy target on `:8002`.
- **llm-copilot** — `VITE_COPILOT_API_BASE`, falls back to the decision-engine base.

Pages marked *mock* still render local fixtures; everything else calls a real
service and shows an explicit error/empty state when it is down.
