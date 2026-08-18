# frontend

React observability dashboard (Doc1 §2 "Observability Dashboard", §3.3 real-time streaming path).
App name: **SHARP**.

**Tech**: React 18, Vite, TypeScript, Tailwind CSS v4 (CSS-first `@theme` config), shadcn/ui
(Radix primitives), Recharts, Zustand, React Router, react-force-graph-3d (three.js). Native
WebSocket is not wired up yet (see Status).

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
│   ├── dependency-graph/    # react-force-graph-3d canvas + ServiceList, lib/severityColors.ts
│   ├── models/              # MLflow run registry + detail dialog
│   ├── notifications/       # header popover + full page, backed by notificationStore
│   ├── settings/            # 5 tabs: thresholds, model, integrations, notifications, security
│   ├── profile/             # account details + mock API tokens
│   └── copilot/             # components/CopilotChat.tsx, CopilotPage.tsx
├── App.tsx                 # react-router routes; marketing/graph/copilot are lazy loaded
└── main.tsx                 # BrowserRouter + root render
```

**Route-level code splitting**: `MarketingPage`, `DependencyGraphPage` and `CopilotPage` are
`lazy()`-loaded in `App.tsx` so the hero video wiring, three.js (via `react-force-graph-3d`), and
the heaviest framer-motion usage stay out of the shared bundle. The `DependencyGraphPage` chunk is
~1.4 MB alone — worth knowing before adding anything else heavy there. The
`.then(m => ({ default: m.X }))` wrapper preserves the
named-export convention every page uses. `Suspense` falls back to `shared/components/RouteFallback`.

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
- **The hero video is a third-party CloudFront asset** (13.9 MB) hotlinked per the reference spec.
  It is wrapped in defences: a gradient painted behind it, `onError` swapping to that gradient,
  and it is skipped entirely under `prefers-reduced-motion`. Verified to still look correct with
  the URL blocked. The `HeroSection` `<section>` carries `isolate` — **this is load-bearing**:
  without its own stacking context the negative-z-index video escapes and paints behind the page
  root's `bg-black`, rendering the hero pure black even though the video decodes fine.
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

**Dependency graph** (`features/dependency-graph/`) is a 3D force graph via
`react-force-graph-3d` (wraps `3d-force-graph`/three.js with React props), following Doc4 P-13's
node/edge semantics with the rendering approach adapted for three dimensions:

- **`react-force-graph-3d` only, not the full `react-force-graph` umbrella** — that package also
  ships 2D/VR/AR renderers this project doesn't use. `cytoscape.js` was ruled out (2D only) and
  `d3-3d` is a projection helper, not a force engine. The route is `lazy()`-loaded (see below), so
  three.js never touches the shared bundle.
- **`lib/severityColors.ts` resolves the oklch severity tokens to concrete `rgb()` at runtime.**
  three.js's `Color` doesn't parse `oklch()`, and — verified against Playwright's bundled
  Chromium — `getComputedStyle` echoes `oklch(...)` back unchanged rather than normalising it, so
  reading the CSS variable directly isn't enough. The fix: paint the token onto a 1x1 `<canvas>`
  and read back `getImageData`, which always returns concrete 8-bit RGB regardless of input colour
  space. Memoised per session.
- **`DependencyGraph3D` deep-clones `graphNodes`/`graphEdges` per mount.** The library mutates
  whatever objects it's given (adds `x/y/z/vx/vy/vz`, replaces link `source`/`target` strings with
  node references), and those constants are shared with the dashboard's mock data.
- **`ServiceList` restores keyboard access.** A WebGL canvas is one DOM node, so the per-node
  `role="button"` the old 2D SVG graph had is gone. The list sitting beside the canvas is
  focusable/Enter-activatable per row and syncs hover state with the 3D nodes — this is a
  deliberate accessibility replacement, not a decorative addition.
- **Screenshot stability, verified**: `cooldownTicks={100}` settles the physics quickly; two
  screenshots taken after settle are pixel-identical except the deliberately-animated particle on
  the critical edge. Four repeated navigate-away-and-back cycles produced no WebGL console errors
  (context leak check).

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
