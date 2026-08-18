# frontend

React observability dashboard (Doc1 §2 "Observability Dashboard", §3.3 real-time streaming path).
App name: **SHARP**.

**Tech**: React 18, Vite, TypeScript, Tailwind CSS v4 (CSS-first `@theme` config), shadcn/ui
(Radix primitives), Recharts, Zustand, React Router, d3-force. Native WebSocket is not wired up
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
│   ├── components/        # Logo, Sparkline, SeverityBadge, NotFoundPage, RouteFallback
│   ├── hooks/             # useCountUp, useResizeObserver
│   ├── store/             # uiStore (sidebar), notificationStore (unread state)
│   ├── brand.ts           # PRODUCT_NAME, REPO_NAME, ORG_NAME -- the brand strings
│   └── types.ts           # Severity -- the cross-feature domain type
├── features/
│   ├── marketing/          # public landing page at / -- NOT inside AppShell
│   ├── auth/                # LoginPage, SignupPage, ForgotPasswordPage + AuthLayout
│   ├── dashboard/           # components/, data/mockData.ts, types.ts, DashboardPage.tsx
│   ├── services/            # (same shape)
│   ├── incidents/           # reads ?filter=<serviceId> from the dependency graph
│   ├── dependency-graph/    # 2D SVG canvas, headless d3-force layout in lib/runLayout.ts
│   ├── models/              # MLflow run registry + detail dialog
│   ├── notifications/       # header popover + full page, backed by notificationStore
│   ├── settings/            # 5 tabs: thresholds, model, integrations, notifications, security
│   ├── profile/             # account details + mock API tokens
│   └── copilot/             # components/CopilotChat.tsx, CopilotPage.tsx
├── App.tsx                 # react-router routes; marketing/graph/copilot are lazy loaded
└── main.tsx                 # BrowserRouter + root render
```

**Route-level code splitting**: `MarketingPage`, `DependencyGraphPage` and `CopilotPage` are
`lazy()`-loaded in `App.tsx` so `d3-force` and the heaviest framer-motion usage stay out of the
shared bundle. The `.then(m => ({ default: m.X }))` wrapper preserves the named-export convention
every page uses. `Suspense` falls back to `shared/components/RouteFallback`.

Dashboard content maps Doc1/Doc4's actual documented dashboard pieces onto mock
self-healing-framework data (not generic SaaS metrics): 4 stat cards, a recovery-actions bar
chart, an anomaly-score trend line chart with reference lines at 0.5/0.85 (matches
`AnomalyScoreChart`'s spec in `docs/prompts/Doc4_Claude_Code_Agent_Prompts.md` P-12 exactly),
`ServiceHealthGrid`, `IncidentFeed`, and a dismissible `DriftAlertBanner`. Severity colours use
named Tailwind tokens (`status-watch/warn/degrade/critical/healthy`) defined in `src/index.css`,
matching root `CLAUDE.md`'s thresholds (`<0.5` watch, `0.5-0.7` warn, `0.7-0.85` degrade,
`>0.85` critical) so real data can drop in later without a colour-mapping rewrite.

**Marketing page** (`features/marketing/`, route `/`) is adapted from three pasted references (a
SaaS hero template, a single-viewport video-background landing spec, and later a full "Oracle
red, Nucleus-style" SaaS design screenshot the section structure now follows). Section order:
`MarketingNav` → `HeroSection` → `TechMarquee` → `HowItWorks` → `IntegratedPlatform` →
`FeatureGrid` → `SeverityLadder` → `HospitalAnalogy` → `ProductShowcase` →
`IntegrationsSection` → `ResearchComponents` → `CtaBand` → `MarketingFooter`. The reference's
testimonial and blog sections were explicitly not built. Decisions worth knowing:

- **It is a React route, not the standalone `index.html`/`styles.css`/`main.js` the first
  reference specified** — one codebase, one build, and Sign in / Sign up route to the real auth
  pages. Reference *visual language* was kept, file structure was not.
- **`TechMarquee` (was `TrustRow`) and `IntegratedPlatform` (was `TechStack`) replace fabricated
  content, not just restyle it.** The design references show enterprise customer logos and a
  generic capability diagram; this is a research project with no customers, so `TechMarquee` lists
  what SHARP actually runs on (Kubernetes, Prometheus, MLflow, …) and `IntegratedPlatform` is the
  real six-layer architecture with a connector-line list plus a layered graphic built from plain
  CSS, not a new charting/diagram dependency.
- **The stat row deliberately excludes accuracy.** `ml-pipeline/RESULTS.md` measures F1 at 0.5663
  on the single tuned entity but 0.1195 averaged across all 28, so any headline accuracy number
  would be either cherry-picked or bad. Throughput (~450 eps), update cost (O(1)), detection SLO
  (<60s) and benchmark coverage (28 entities) are all doc-grounded and honest. **Do not add an
  accuracy stat here** without reading RESULTS.md's "Reading these numbers honestly" section. It
  now sits as a thin strip under the hero screenshot rather than a headline claim.
- **The hero has no background video.** An earlier pass hotlinked a 13.9 MB third-party CloudFront
  asset per a reference spec; it was removed per feedback in favour of an ambient background built
  from the app's own tokens — two `animate-blob-drift` blobs in `status-healthy`/`status-warn` at
  low opacity, plus a faint CSS grid-line texture. The `HeroSection` `<section>` still carries
  `isolate` — **this is load-bearing**: without its own stacking context the negative-z-index
  blobs escape and paint behind the page root's `bg-black` instead of inside the hero.
- **The primary CTA's glow shadow is `oklch(0.75 0.18 150/35%)`, a literal, not
  `var(--color-status-healthy)`.** Tailwind's `/opacity` modifier on an arbitrary value doesn't
  reliably apply to a `var()` reference the same way it does to a named colour utility, and
  Tailwind arbitrary values fail *silently* (no CSS emitted, no build error) rather than erroring —
  the same class of bug the missing `--destructive` token hit earlier. The oklch value is copied
  from `index.css`'s `.dark` block; if that token's dark-mode value ever changes, update this too.
- **`FeatureGrid`'s decorative corner pattern uses a seeded PRNG, not `Math.random()`** — this
  project avoids non-determinism in anything that renders (the dependency graph layout and the
  incident trend chart do the same) so screenshots stay reproducible.
- **`public/marketing/*.png` are real screenshots of this app**, captured with Playwright, not
  stock images — recapture them (`/dashboard`, `/dependency-graph`) after any visual change to the
  sidebar, Logo, or dependency graph so they don't go stale.

`Logo` (`shared/components/Logo.tsx`) is the single source of truth for the brand mark, replacing
five separate `<img src="/favicon.svg">` call sites that each duplicated the wrapper and had
inconsistent backgrounds (white circle on marketing vs `bg-primary` in the app shell). The
wordmark is **hand-authored as SVG line segments, not rendered from a font** — `--font-sans` is a
system stack, so a font-rendered wordmark would differ across OSes, unacceptable for a logo.
Letterforms are original; only the proportions (wide, geometric, tight tracking) took a cue from
an Oracle-style reference the user provided. `variant="mark"` (icon only) is used in the collapsed
sidebar so the brand isn't hidden entirely, which is what happened before.

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

**Dependency graph** (`features/dependency-graph/`) is a 2D SVG canvas following Doc4 P-13, with
one documented divergence and two interaction enhancements beyond the P-13 spec:

- **The simulation runs headless.** P-13 says never to drive React state from simulation ticks.
  Rather than mutating the SVG DOM directly — which would create a second source of truth for node
  positions and complicate the tooltip and click handlers — `lib/runLayout.ts` stops the
  `d3-force` simulation and ticks it synchronously to convergence, then returns positions once.
  Zero React renders during ticks, one source of truth, deterministic layout. Pure function called
  from `useMemo`, so ResizeObserver-driven re-centring is free.
- **Hover/focus highlights connected nodes and edges.** `DependencyGraphCanvas` computes the set of
  node ids and edge keys directly connected to the hovered node and dims everything else
  (`opacity` + `transition-opacity`), so tracing what a service depends on is a glance instead of a
  squint. Not in P-13's spec — added because a static graph with six same-weight nodes is hard to
  read at rest.
- **Pan and zoom.** Drag the background `<rect>` (a sibling of the nodes, never an ancestor, so it
  can't intercept clicks on them) to pan; scroll to zoom, centred on the cursor; or use the
  corner +/−/reset buttons. **Wheel zoom needs a native `addEventListener('wheel', ..., {passive:
  false})` in a `useEffect`** — React's `onWheel` prop is passive by default, so calling
  `preventDefault()` inside it is a silent no-op and the page scrolls right along with the zoom.
- A 3D version (`react-force-graph-3d`/three.js) was tried and reverted per feedback that it didn't
  suit the product — worth knowing if this comes up again, since the oklch→three.js colour
  resolution problem and the "WebGL canvas has no per-node focus" accessibility gap it required
  working around are both solved problems if anyone revisits 3D: see git history around the
  revert commit for the approach (canvas `getImageData` colour resolution, a focusable sibling
  list for keyboard parity).

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

**No custom font yet** — `--font-sans` in `src/index.css`'s `@theme inline` block is a system font
stack placeholder, deliberately isolated to one token so swapping in a real font later is a
one-line change, not a find-and-replace. The marketing page used to have a separate
`--font-display` dot-matrix headline face (third-party OnlineWebFonts CDN) but that token, the
`<link>` tags in `index.html`, and every `font-display` class site were removed — the whole app
uses one font family now.

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
