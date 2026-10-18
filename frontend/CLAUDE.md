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

**Status**: every route is a real page. The pages split into live ones and mock ones:
- **Live** (from `services/ml-backend`, with a mock fallback): Dashboard (service grid, stat cards,
  drift banner, anomaly trend), Models (`LiveModelDetailDialog`: version history, rollback, restore,
  validity check), the **Model lifecycle** page (`features/lifecycle/`, live only, no mock) and the
  **Logs** page (`features/logs/`, live only): a Railway style log viewer with a filter box
  (`service:` / `level:` / `source:` terms plus free text, parsed in `lib/filter.ts` exactly as the
  backend does), a level histogram, live tail over the WebSocket (`subscribeToMessages("log")` in
  `useLiveConnection`, which keeps log lines out of `liveStore`), paging back on scroll-up, and
  download. Triggers there are native `<button>`s because shadcn's `Button` does not forward refs
  under React 18 and Radix tooltips and menus need one.
- **Wiring**: `src/lib/api.ts` (typed REST), `src/hooks/useLiveConnection.ts` (one app-wide
  WebSocket on `/ws/events`, backoff 1 to 30 s, plus a 4 s REST poll; messages are batched every
  250 ms) and `src/shared/store/liveStore.ts`. Pages use mock data only while `ready` is false; the
  header `LiveStatusBadge` shows Live / Reconnecting / Offline. Vite proxies `/api` and `/ws` to
  :8002 (ml-backend; main's `lib/api.ts` calls the decision engine on :8000 directly).
- **Still mock**: Incidents, recovery actions, the remediation simulation, the copilot, auth and
  settings.

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
`MarketingNav` → `HeroSection` → `TechMarquee` → `HowItWorks` → `RolloutPath` →
`IntegratedPlatform` → `FeatureGrid` → `SeverityLadder` → `HospitalAnalogy` → `ProductShowcase` →
`IntegrationsSection` → `ResearchComponents` → `CtaBand` → `MarketingFooter`. The reference's
testimonial and blog sections were explicitly not built. Decisions worth knowing:

- **`RolloutPath`** is adapted from a pasted "PrecisionSection" reference spec (light-theme,
  rainbow-gradient, absolutely-positioned vw-based staircase of pillars, plus an external font/
  background-image/logo-icon none of which belong in this app). Kept the structural idea — desktop
  staircase via absolute positioning, mobile alternating left/right flow, switched by breakpoint —
  discarded everything else: dark tokens instead of the light palette, a single `brand-primary`
  gradient line instead of the 6-color rainbow, lucide icons instead of a repeated external PNG,
  and real content instead of aerospace-facility placeholder copy. **The content is deliberately
  not the same as `HowItWorks`'s Ingest/Predict/Decide/Act loop** — that section is what SHARP does
  at runtime; `RolloutPath` (`ROLLOUT_PILLARS` in `marketingContent.ts`) is how a team actually
  adopts it (Scope → Integrate → Certify → Activate), a genuinely different piece of information.
  Desktop pillar positions are **percentages of the section's own box, not viewport units** — the
  source spec's `vw` values were calibrated against the raw browser width, which would have made
  the staircase misaligned with this page's consistent `max-w-6xl` column; converted to `leftPct`/
  `bottomPct` in the data so it stays scoped to the same container every other section uses.
- **`MarketingFooter`** is adapted from a pasted "Site Footer" reference spec (black-canvas
  aerospace-company footer: animated dotted top strip, big tagline, oversized wordmark brand row).
  Structure kept, content and color replaced: `bg-background`/`text-foreground` tokens instead of
  literal `#000`/`#fff`, the real `Wordmark`/`LogoMark` (now exported from `Logo.tsx` specifically
  for this oversized use) instead of a font-rendered brand name, and the three nav columns point at
  real things — `PLATFORM_LINKS` and `ACCOUNT_LINKS` are the same links the footer already had;
  the third column (was "Company"/social links: Our Team, News, Careers, LinkedIn, X) is now
  **`PROJECT_LINKS`, a single real link to this repo's actual GitHub remote** — SHARP is a research
  project, not a company with a social-media presence, so nothing was invented in place of "social
  links". The legal line's `#privacy`/`#terms` were dropped for the same reason: this project has
  no such pages, and dead anchors would contradict the honesty this page tries to keep elsewhere
  (see `ResearchComponents`'s honest status badges, the stat row's excluded accuracy figure). The
  dotted top strip is `.footer-dots-line` in `index.css` (three layered `radial-gradient`s + a
  `footer-dots-move` keyframe, `--animate-footer-dots`) — kept as plain CSS rather than Tailwind
  utilities since a multi-layer gradient background doesn't have a clean utility-class form, and
  scoped to exactly one element. Rendered in neutral `--color-foreground` at low opacity, **not**
  brand green — this is background texture, not a "small accent," so it stays outside the sparse-
  green allowance the rest of the page follows.

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
- **The hero had no background video, then no ambient blobs either, and now has a WebGL beams
  effect instead.** An earlier pass hotlinked a 13.9 MB third-party CloudFront video asset, then
  replaced it with two `animate-blob-drift` blobs plus a grid-line texture; both were removed in
  the SHARP design system pass (DESIGN.md's source discipline is "no atmospheric gradients"). The
  hero later read as too flat, so `features/marketing/components/Beams.tsx` was added — a
  react-bits "Beams" component (vertical light-beam strips warped by Perlin noise, WebGL via
  `three`/`@react-three/fiber`/`@react-three/drei`), ported from JS to TS with the shader-patching
  internals (`extendMaterial`) left loosely typed on purpose since ShaderLib's header-injection
  pattern doesn't map onto a precise TS shape. This is treated as *directional light*, not an
  atmospheric color wash, so it doesn't reopen the no-gradients rule the way the old blobs did.
  Rendered in an `absolute inset-x-0 top-0 h-[700px]` layer behind the hero text only (not the
  screenshot/stats below), with a `mask-image` fade so it doesn't cut off abruptly, and skipped
  entirely when `useReducedMotion()` is true. Two adaptations from the vendored source: a
  `backgroundColor` prop (default `#0a0a0a`) was added so the canvas's clear color matches
  `--background`'s actual rendered value (`oklch(0.145 0 0)` ≈ `#0a0a0a`, not pure `#000000` —
  without this there'd be a faint seam where the canvas meets the rest of the page), and
  `lightColor="#50C878"` was kept as a literal hex (not `var(--brand-primary)`) because Three.js
  material colors are JS-side numeric values, not CSS, so a live CSS custom property can't feed
  them directly. **This is the heaviest dependency in the app**: the `MarketingPage` lazy chunk
  grew from a few KB to ~905 KB (~245 KB gzip) because of `three`; confirmed via `pnpm run build`
  that this cost is fully contained in that chunk and the shared `index-*.js` bundle every
  authenticated page loads is unaffected. `isolate` was dropped from the `HeroSection` `<section>`
  back when the blobs were removed and hasn't been reintroduced — Beams doesn't need it since it's
  a normal (non-negative) z-index layer, not a negative-z-index background trick.
- **`TechMarquee`'s "Built on" strip has real brand logos, monochrome.** `MARQUEE_ITEMS` in
  `marketingContent.ts` is now `{ label, icon? }[]` instead of `string[]`, with `icon` pulled from
  the `simple-icons` package (tree-shakable named ESM exports like `siKubernetes` — confirmed via a
  real `pnpm run build` that only the ~7 icons actually imported end up in the bundle, not the
  whole 3,471-icon package: the `MarketingPage` chunk grew by only ~13 KB raw). Rendered through
  `ToolIcon.tsx`, a two-line wrapper that forces `fill="currentColor"` so every logo inherits the
  surrounding `text-foreground/50` instead of showing each tool's own brand color — kept monochrome
  on purpose, consistent with the sparse-color rule elsewhere on this page. **`river` and `YARP`
  stay text-only** — neither has a real brand mark anywhere (river is a niche Python library, YARP
  is an internal Microsoft project) — confirmed by checking simple-icons' own icon list rather than
  guessing, and deliberately not given a fake/generic icon just to make every item visually match.
  This same treatment was *not* applied to `IntegrationsSection`'s chips — user chose to scope this
  to the marquee only for now.
- **The primary CTA is a flat `bg-brand-primary` fill, no glow.** It used to carry a
  `shadow-[...oklch(0.75_0.18_150/35%)...]` glow — an arbitrary-value opacity modifier on a literal
  oklch, kept as a literal rather than `var()` because Tailwind's `/opacity` modifier doesn't
  reliably apply to a `var()` reference (same silent-failure class as the missing `--destructive`
  token: no CSS emitted, no build error). Removed entirely in the design-system pass, not fixed —
  DESIGN.md's own components have no glow/shadow on buttons, so the whole pattern is gone rather
  than made to work correctly.
- **`FeatureGrid`'s decorative corner pattern uses a seeded PRNG, not `Math.random()`** — this
  project avoids non-determinism in anything that renders (the dependency graph layout and the
  incident trend chart do the same) so screenshots stay reproducible.
- **`public/marketing/*.png` are real screenshots of this app**, captured with Playwright, not
  stock images — recapture them (`/dashboard`, `/dependency-graph`) after any visual change to the
  sidebar, Logo, or dependency graph so they don't go stale.

**SHARP design system (marketing-first, `DESIGN.md` at repo root).** The marketing page was
rebuilt against a design-system analysis of Supabase's marketing site (`DESIGN.md`, adapted onto
SHARP's own tokens rather than copied literally), with three deliberate departures from the
source:

- **Canvas stays dark, not white.** DESIGN.md documents a light system; SHARP inverts its polarity
  (near-black canvas, near-white ink, reusing the existing `.dark` `--background`/`--foreground`)
  while keeping its rigor — one green accent, no gradients, screenshots as decoration, square-ish
  radii, tracked type. Every other already-built page (dashboard, services, incidents, …) stays on
  the existing dark tokens; only `features/marketing/` has been migrated so far. If it reads well,
  the same system is expected to extend to the rest of the app next — check before assuming a
  non-marketing page follows these conventions.
- **Green is sparse, by rule, with two named exemptions.** Reserved for the primary CTA fill, the
  Logo mark, and small accent dots/pills — "one filled green button per viewport" is enforced by
  hand (e.g. `MarketingNav`'s Sign Up button is deliberately the shared `Button`'s neutral
  `default` variant, not green, because the nav is `fixed` and co-visible with whichever section's
  own green CTA is in view). `SeverityLadder`'s four severity colours and
  `ResearchComponents`' "Complete" status badge are **exempt** — they're a different semantic
  system (service health / progress state, `status-*` tokens), not brand colour, and were never in
  scope for the sparse-green rule. Don't conflate the two systems even though `brand-primary`
  currently aliases the same hue as `status-healthy`.
- **New tokens are additive, not replacements.** `index.css`'s `.dark` block gained
  `--brand-primary` (aliased *by reference* to `var(--status-healthy)`, not a duplicated oklch
  literal — same visual value, kept as a separate name since "brand action colour" and "service
  health colour" are different semantic intents that only happen to share a hue today),
  `--brand-primary-deep` (hover/pressed), and `--brand-on-primary` (near-black text on the green
  fill — deliberate, survives the canvas inversion unchanged since only the canvas polarity
  flipped, not the button's dark-on-green pairing). A parallel `--radius-brand-xs/sm/md/lg/xl`
  scale (4/6/8/12/16px) was added rather than touching the global `--radius` that shadcn
  `Button`/`Card` depend on everywhere else — marketing components use `rounded-brand-*`, nothing
  else changed radius. Buttons use `rounded-brand-sm` (square-ish, 6px); pills/tags/badges keep
  `rounded-full` — DESIGN.md draws this exact distinction and it was applied file-by-file (see
  `IntegrationsSection.tsx`, which has one of each in the same file).

`Logo` (`shared/components/Logo.tsx`) is the single source of truth for the brand mark, replacing
five separate `<img src="/favicon.svg">` call sites that each duplicated the wrapper and had
inconsistent backgrounds (white circle on marketing vs `bg-primary` in the app shell, later
unified to a light `bg-primary` badge everywhere). The badge is now `bg-brand-badge`, a dark navy
(`#0f172a`) matching `public/favicon.svg`'s hardcoded `rect fill` exactly, so the browser tab icon
and every in-app instance of the mark read as the same badge — the favicon file itself can't read
a CSS custom property (it's a static SVG, not processed by Tailwind), so `--brand-badge` in
`index.css` is a plain hex kept in manual sync with that file rather than the usual `oklch()`. The
wordmark **used to be hand-authored SVG line segments, not rendered from a font** —
`--font-sans` was a system stack when this was decided, so a font-rendered wordmark would have
differed across OSes; the letterforms were original, wide and geometric with an Oracle-style
proportion cue. Once Inter loaded globally that reasoning stopped applying, and the hand-drawn
strokes read as technical/wireframe line art rather than a clean brand mark. `Wordmark` is now a
plain `<span>SHARP</span>` in `font-sans font-semibold tracking-tight` — Supabase's logotype was
the reference point for "looks like real typography, not a schematic" — which renders consistently
because Inter itself is loaded everywhere, the same guarantee the SVG used to provide a different
way. The oversized footer instance (`MarketingFooter`'s brand row) overrides the tracking to
`tracking-hero` for a tighter look at that scale; `cn()`'s `twMerge` resolves the conflict with the
base `tracking-tight`, last one in the merged class list wins. `variant="mark"` (icon only, the
triangle `LogoMark` — unchanged by this pass) is used in the collapsed sidebar so the brand isn't
hidden entirely, which is what happened before.

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

**Font is Inter**, loaded via Google Fonts `<link>` tags in `index.html` (weights `400;500;600` —
deliberately wide so nothing synthetic-bolds `font-semibold` UI elements) and set as
`--font-sans` in `src/index.css`'s `@theme inline` block, one token, applies everywhere. True
section headings (`<h1>`/`<h2>`) additionally take `font-medium` (500) + `tracking-hero`/
`tracking-display` (-0.03em/-0.02em) per the SHARP design system above — currently applied across
`features/marketing/` only; buttons, badges, and stat numbers (`StatsRow`) intentionally stay
`font-semibold`. The marketing page used to have a separate `--font-display` dot-matrix headline
face (third-party OnlineWebFonts CDN) but that token, the old `<link>` tags, and every
`font-display` class site were removed before Inter was adopted.

**Build next**. The UI surface is complete; what's left is wiring it to something real.
1. ~~WebSocket hook~~ done: `src/hooks/useLiveConnection.ts`
2. Real API/WebSocket wiring to replace every `features/*/data/mockData.ts` — agree the JSON
   schema (`anomaly_score`, `action_receipt`, `drift_alert`) with `services/ml-backend`'s
   `app/api/websocket.py` first, write it down in `docs/API.md`
3. Wire `CopilotChat` to a real backend: SSE streaming (Doc4 P-14) to replace the mocked
   "thinking" timeout, plus a message transcript (currently just a composer, no history)
4. Real auth behind `features/auth/` — the three pages are UI only and navigate to `/dashboard`
   on submit without validating anything. Nothing guards the authenticated routes.
5. Settings and profile forms don't persist — every input is `defaultValue`, no submit handler.
   Needs a store plus a real config endpoint.
6. ~~Models promote/rollback~~ done for live models (`LiveModelDetailDialog`); mock mode still only appends a local message; hook to P-06's
   `POST /models/{service_id}/promote|rollback`
7. Playwright E2E once there's a real backend to test against
8. `Sidebar`/`AppShell` don't auto-collapse below a breakpoint (checked at 390px). The marketing
   page is responsive; the authenticated shell is not yet. `sheet` is the obvious primitive.
9. The shared bundle is still ~940 KB. The three heaviest routes are split out already; Recharts
   and the Radix surface in the shell are the next candidates. Separately, the `MarketingPage`
   lazy chunk is now its own ~905 KB (~245 KB gzip) outlier because of `three`/Beams (see
   "Marketing page" above) — it doesn't add to the shared bundle, but if the hero background is
   ever revisited for perf, that's the chunk to look at.
