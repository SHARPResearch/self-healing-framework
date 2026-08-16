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

Dashboard (`/dashboard`, also the default route), Incidents (`/incidents`), and Copilot
(`/copilot`) are real, built with mock data. Other nav items are "coming soon" stubs — real
content, API wiring, and auth are follow-up work.
