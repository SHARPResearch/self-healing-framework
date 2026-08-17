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

**Status**: every route is a real page now, all built on mock data (no backend, WebSocket, LLM
or auth is wired up). `ComingSoonPage`/`StubRoute` are gone — there is nothing left to stub.

```
src/
├── components/ui/        # 21 shadcn primitives (button, card, badge, avatar, separator,
│                          # collapsible, dropdown-menu, tooltip, scroll-area, input, label,
│                          # checkbox, switch, select, tabs, table, dialog, popover,
│                          # progress, skeleton, alert)
├── shared/
│   ├── layout/            # AppShell, Sidebar, Header, navigation.ts (nav groups/items)
│   ├── components/        # Sparkline, SeverityBadge, NotFoundPage, RouteFallback
│   ├── hooks/             # useCountUp, useResizeObserver
│   ├── store/             # uiStore (sidebar), notificationStore (unread state)
│   └── types.ts           # Severity -- the cross-feature domain type
├── features/
│   ├── marketing/          # public landing page at / -- NOT inside AppShell
│   ├── auth/                # LoginPage, SignupPage, ForgotPasswordPage + AuthLayout
│   ├── dashboard/           # components/, data/mockData.ts, types.ts, DashboardPage.tsx
│   ├── services/            # (same shape)
│   ├── incidents/           # reads ?filter=<serviceId> from the dependency graph
│   ├── dependency-graph/    # d3-force layout, lib/runLayout.ts is pure
│   ├── models/              # MLflow run registry + detail dialog
│   ├── notifications/       # header popover + full page, backed by notificationStore
│   ├── settings/            # 5 tabs: thresholds, model, integrations, notifications, security
│   ├── profile/             # account details + mock API tokens
│   └── copilot/             # components/CopilotChat.tsx, CopilotPage.tsx
├── App.tsx                 # react-router routes; marketing/graph/copilot are lazy loaded
└── main.tsx                 # BrowserRouter + root render
```

**Route-level code splitting**: `MarketingPage`, `DependencyGraphPage` and `CopilotPage` are
`lazy()`-loaded in `App.tsx` so the hero video wiring, `d3-force`, and the heaviest framer-motion
usage stay out of the shared bundle. The `.then(m => ({ default: m.X }))` wrapper preserves the
named-export convention every page uses. `Suspense` falls back to `shared/components/RouteFallback`.

Dashboard content maps Doc1/Doc4's actual documented dashboard pieces onto mock
self-healing-framework data (not generic SaaS metrics): 4 stat cards, a recovery-actions bar
chart, an anomaly-score trend line chart with reference lines at 0.5/0.85 (matches
`AnomalyScoreChart`'s spec in `docs/prompts/Doc4_Claude_Code_Agent_Prompts.md` P-12 exactly),
`ServiceHealthGrid`, `IncidentFeed`, and a dismissible `DriftAlertBanner`. Severity colours use
named Tailwind tokens (`status-watch/warn/degrade/critical/healthy`) defined in `src/index.css`,
matching root `CLAUDE.md`'s thresholds (`<0.5` watch, `0.5-0.7` warn, `0.7-0.85` degrade,
`>0.85` critical) so real data can drop in later without a colour-mapping rewrite.

**Marketing page** (`features/marketing/`, route `/`) is adapted from two pasted references (a
SaaS hero template and a single-viewport video-background landing spec). Three decisions worth
knowing:

- **It is a React route, not the standalone `index.html`/`styles.css`/`main.js` the reference
  specified** — one codebase, one build, and Sign in / Sign up route to the real auth pages. The
  reference's *visual language* was kept, its file structure was not. It also scrolls through
  explainer sections rather than staying in one viewport, because it has to actually explain what
  the system does.
- **The stat row deliberately excludes accuracy.** `ml-pipeline/RESULTS.md` measures F1 at 0.5663
  on the single tuned entity but 0.1195 averaged across all 28, so any headline accuracy number
  would be either cherry-picked or bad. Throughput (~450 eps), update cost (O(1)), detection SLO
  (<60s) and benchmark coverage (28 entities) are all doc-grounded and honest. **Do not add an
  accuracy stat here** without reading RESULTS.md's "Reading these numbers honestly" section.
- **The hero video is a third-party CloudFront asset** (13.9 MB) hotlinked per the reference spec.
  It is wrapped in defences: a gradient painted behind it, `onError` swapping to that gradient,
  and it is skipped entirely under `prefers-reduced-motion`. Verified to still look correct with
  the URL blocked. The `HeroSection` `<section>` carries `isolate` — **this is load-bearing**:
  without its own stacking context the negative-z-index video escapes and paints behind the page
  root's `bg-black`, rendering the hero pure black even though the video decodes fine.

`ServiceManagementTable` (`features/services/components/`) is adapted from a pasted VPS/hosting
admin-panel component. Content substitutions from the source: OS icons (Windows/Ubuntu logos)
became `RuntimeIcon` (Node/Python/Go monograms, matching `services/target-services/`'s
documented stack); country flag + physical server location became a k8s namespace; CPU% bars
became `AnomalyScoreBars` colored by the same severity tokens `SeverityBadge` uses; the
active/paused/inactive status pill became `SeverityBadge` itself (watch/warn/degrade/critical);
billing "Due Date" became a replica count; and the generic Stop/Start/Pause/Resume/Restart VPS
power controls became the decision engine's actual action vocabulary (Restart, Scale +1 replica,
Shift traffic), which only append a mock activity-log entry rather than fabricating a severity
change. Row data is a join of the dashboard feature's `ServiceHealth` (live telemetry, single
source of truth) with local `ServiceMetadata` (registry fields a real deployment would source
from the k8s API instead) — see `ServiceRow` in `features/services/types.ts`. The reference
component's rows and modal close button had no keyboard/screen-reader support at all (a plain
`<div onClick>`, no dialog role); this pass added `role="button"`/keyboard handling on rows and
`role="dialog"`/`aria-label`s/Escape-to-close on the detail panel.

`IncidentReportCard` (`features/incidents/components/`) is adapted from a pasted reaviz-based
community component: a time-range-switchable (7/30/90 day) trend chart, critical/total incident
counts, and a reliability metrics row. Two deliberate substitutions from the source component:
the chart uses Recharts (already a dependency, used by the dashboard) instead of adding `reaviz`
as a second charting library, and the generic "Incident Response Time"/"Escalation Rate" metrics
became MTTD/MTTR/escalation rate — the actual detection-loop and graduated-remediation-policy
metrics this project's architecture cares about, not generic ops metrics.

**Dependency graph** (`features/dependency-graph/`) follows Doc4 P-13 with two documented
divergences:

- **`d3-force` only**, not the full `d3` bundle — the page needs `forceSimulation`/`forceLink`/
  `forceManyBody`/`forceCenter` and nothing else, and rendering is React-owned JSX, so
  `d3-selection` (which fights React for DOM ownership) and `d3-drag` are not installed.
- **The simulation runs headless.** P-13 says never to drive React state from simulation ticks.
  Rather than mutating the SVG DOM directly — which would create a second source of truth for node
  positions and complicate the tooltip and click handlers — `lib/runLayout.ts` stops the
  simulation and ticks it synchronously to convergence, then returns positions once. Zero React
  renders during ticks, one source of truth, and a deterministic layout that makes screenshots
  reproducible. It is a pure function called from `useMemo`, so ResizeObserver-driven re-centring
  is free.

The edge list extends Doc3's demo topology by two edges (`orders → payments`, `search →
inventory`). Doc3's four edges only cover four of the six services and omit `service-e-payments`,
the only critical one, which would leave two orphan nodes and mean the pulsing-critical-node and
amber-downstream-edge states never render at all. The addition is flagged in a comment in
`data/mockData.ts`.

`CopilotChat` (`features/copilot/components/CopilotChat.tsx`) is a framer-motion prompt composer
adapted from a pasted community component: animated background blobs, a `/`-triggered command
palette (`/rca`, `/explain`, `/remediate`, `/summarize` — RCA-engine actions, not the original's
UI-builder commands), file attachments, and a mocked "thinking" delay in place of a real
response. No message transcript yet and no LLM/SSE wired up — see "Build next" below.

**Dark mode is the default** (`class="dark"` hard-coded on `<html>` in `index.html`) — no theme
toggle built yet, that's a real follow-up if light mode is ever wanted.

**No custom body font yet** — `--font-sans` in `src/index.css`'s `@theme inline` block is a system
font stack placeholder, deliberately isolated to one token so swapping in a real font later is a
one-line change, not a find-and-replace. `--font-display` is separate and is the marketing page's
dot-matrix headline face; don't conflate the two.

**Build next**. The UI surface is complete; what's left is wiring it to something real.
1. `src/hooks/useWebSocket.ts` — native WebSocket, exponential backoff reconnect (1s→2s→4s→max 30s)
2. Real API/WebSocket wiring to replace every `features/*/data/mockData.ts` — agree the JSON
   schema (`anomaly_score`, `action_receipt`, `drift_alert`) with `services/ml-backend`'s
   `app/api/websocket.py` first, write it down in `docs/API.md`
3. Wire `CopilotChat` to a real backend: SSE streaming (Doc4 P-14) to replace the mocked
   "thinking" timeout, plus a message transcript (currently just a composer, no history)
4. Real auth behind `features/auth/` — the three pages are UI only and navigate to `/dashboard`
   on submit without validating anything. Nothing guards the authenticated routes.
5. Settings and profile forms don't persist — every input is `defaultValue`, no submit handler.
   Needs a store plus a real config endpoint.
6. Models promote/rollback buttons only append a local message; hook to P-06's
   `POST /models/{service_id}/promote|rollback`
7. Playwright E2E once there's a real backend to test against
8. `Sidebar`/`AppShell` don't auto-collapse below a breakpoint (checked at 390px). The marketing
   page is responsive; the authenticated shell is not yet. `sheet` is the obvious primitive.
9. The shared bundle is still ~940 KB. The three heaviest routes are split out already; Recharts
   and the Radix surface in the shell are the next candidates.
