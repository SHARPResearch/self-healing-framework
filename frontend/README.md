# frontend

SHARP — React 18 + Vite + TypeScript + Tailwind v4 + shadcn/ui observability dashboard
(Doc1 §2 "Observability Dashboard"). See `CLAUDE.md` in this folder for the folder architecture
(feature-based, a deliberate deviation from Doc2) and what to build next.

## Quick start

```bash
pnpm install
pnpm dev      # http://localhost:5173
pnpm build    # typecheck + production build
```

## Routes

| Route | What it is |
|---|---|
| `/` | Public marketing landing page (outside the app shell) |
| `/login`, `/signup`, `/forgot-password` | Auth UI — mock only, submitting goes to `/dashboard` |
| `/dashboard` | Stat cards, recovery-action and anomaly-score charts, service health, incident feed |
| `/services` | Service table with a detail panel and mock remediation actions |
| `/dependency-graph` | `d3-force` graph, click a node to filter incidents |
| `/incidents` | Incident report, trend chart, reliability metrics, `?filter=` support |
| `/models` | MLflow run registry with params, metrics and a detail dialog |
| `/notifications` | Full notification history with filters (also a header popover) |
| `/settings` | Thresholds, model, integrations, notifications, security |
| `/profile` | Account details and mock API tokens |
| `/copilot` | Chat composer with a command palette |

**Everything is mock data.** No backend, WebSocket, LLM or authentication is wired up — the auth
pages guard nothing. See `CLAUDE.md` for what's left to connect.
