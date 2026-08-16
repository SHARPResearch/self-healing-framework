# frontend

React observability dashboard (Doc1 §2 "Observability Dashboard", §3.3 real-time streaming path).
App name: **SHARP**.

**Tech**: React 18, Vite, TypeScript, Tailwind CSS v4 (CSS-first `@theme` config), shadcn/ui
(Radix primitives), Recharts, Zustand, React Router. D3.js and native WebSocket are not wired up
yet (see Status).

**Folder architecture: feature-based, not Doc2's flat type-based layout.** Doc2 shows
`components/dashboard/`, `hooks/`, `stores/`, `types/` as separate top-level folders; this repo
uses `src/features/<feature>/{components,data,types.ts,*.tsx}` instead, with only
`src/components/ui/` (shadcn primitives) and `src/shared/` (AppShell, Sidebar, Header,
Sparkline, SeverityBadge, ComingSoonPage, the ui zustand store) staying flat/shared across
features. Chosen deliberately: the app already has 4+ genuinely distinct page domains
(Dashboard, Incidents, Models, Copilot), each better served owning its own
components/data/types together than being split across four parallel folders. If you're
following Doc2 literally for another part of this repo, this folder is the documented exception.

**Status**: Dashboard, Incidents, and Copilot pages are real, built with mock data/mock responses
(no backend/WebSocket/LLM wired up yet). Everything else is a single-line "coming soon" stub
reachable via the sidebar nav, wired into routing so the shell is genuinely navigable:

```
src/
├── components/ui/        # shadcn primitives (button, card, badge, avatar, separator,
│                          # collapsible, dropdown-menu, tooltip, scroll-area)
├── shared/
│   ├── layout/            # AppShell, Sidebar, Header, navigation.ts (nav groups/items)
│   ├── components/        # Sparkline (plain SVG), SeverityBadge, ComingSoonPage
│   └── store/uiStore.ts   # zustand: sidebar collapsed state
├── features/
│   ├── dashboard/          # the real page -- components/, data/mockData.ts, types.ts, DashboardPage.tsx
│   ├── incidents/           # the real page -- components/, data/mockData.ts, types.ts, IncidentsPage.tsx
│   ├── copilot/             # the real page -- components/CopilotChat.tsx, CopilotPage.tsx
│   └── auth/LoginStubPage.tsx
├── App.tsx                 # react-router routes
└── main.tsx                 # BrowserRouter + root render
```

Dashboard content maps Doc1/Doc4's actual documented dashboard pieces onto mock
self-healing-framework data (not generic SaaS metrics): 4 stat cards, a recovery-actions bar
chart, an anomaly-score trend line chart with reference lines at 0.5/0.85 (matches
`AnomalyScoreChart`'s spec in `docs/prompts/Doc4_Claude_Code_Agent_Prompts.md` P-12 exactly),
`ServiceHealthGrid`, `IncidentFeed`, and a dismissible `DriftAlertBanner`. Severity colours use
named Tailwind tokens (`status-watch/warn/degrade/critical/healthy`) defined in `src/index.css`,
matching root `CLAUDE.md`'s thresholds (`<0.5` watch, `0.5-0.7` warn, `0.7-0.85` degrade,
`>0.85` critical) so real data can drop in later without a colour-mapping rewrite.

`IncidentReportCard` (`features/incidents/components/`) is adapted from a pasted reaviz-based
community component: a time-range-switchable (7/30/90 day) trend chart, critical/total incident
counts, and a reliability metrics row. Two deliberate substitutions from the source component:
the chart uses Recharts (already a dependency, used by the dashboard) instead of adding `reaviz`
as a second charting library, and the generic "Incident Response Time"/"Escalation Rate" metrics
became MTTD/MTTR/escalation rate — the actual detection-loop and graduated-remediation-policy
metrics this project's architecture cares about, not generic ops metrics.

`CopilotChat` (`features/copilot/components/CopilotChat.tsx`) is a framer-motion prompt composer
adapted from a pasted community component: animated background blobs, a `/`-triggered command
palette (`/rca`, `/explain`, `/remediate`, `/summarize` — RCA-engine actions, not the original's
UI-builder commands), file attachments, and a mocked "thinking" delay in place of a real
response. No message transcript yet and no LLM/SSE wired up — see "Build next" below.

**Dark mode is the default** (`class="dark"` hard-coded on `<html>` in `index.html`) — no theme
toggle built yet, that's a real follow-up if light mode is ever wanted.

**No custom font yet** — `--font-sans` in `src/index.css`'s `@theme inline` block is a system
font stack placeholder, deliberately isolated to one token so swapping in a real font later is a
one-line change, not a find-and-replace.

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 6, remaining items):
1. `src/hooks/useWebSocket.ts` — native WebSocket, exponential backoff reconnect (1s→2s→4s→max 30s)
2. Real API/WebSocket wiring to replace `features/dashboard/data/mockData.ts` — agree the JSON
   schema (`anomaly_score`, `action_receipt`, `drift_alert`) with `services/ml-backend`'s
   `app/api/websocket.py` first, write it down in `docs/API.md`
3. Real content for the remaining stub pages: Services, Dependency graph (D3.js force-directed,
   per Doc4 P-13), Models, Settings
3b. Wire `CopilotChat` to a real backend: SSE streaming (Doc4 P-14) to replace the mocked
   "thinking" timeout, plus a message transcript (currently just a composer, no history)
4. Real auth to replace `features/auth/LoginStubPage.tsx`
5. Playwright E2E once there's a real backend to test against
6. `Sidebar`/`AppShell` don't auto-collapse below a breakpoint yet (checked at 390px width during
   Incidents page verification) — pre-existing across every page, not specific to one feature
