# frontend

React observability dashboard (Doc1 §2 "Observability Dashboard", §3.3 real-time streaming path).

**Tech**: React 18, Vite, TypeScript, Tailwind CSS, Recharts, D3.js, Zustand, native WebSocket.

**Status**: placeholder only (`package.json` with an echo script). No Vite project yet.

**Build next** (`docs/Doc3_Execution_Guide.md` Phase 1 & 6, in order):
1. `pnpm create vite . --template react-ts` + `pnpm add tailwindcss @tailwindcss/vite recharts d3 zustand axios`
2. `src/hooks/useWebSocket.ts` — native WebSocket, exponential backoff reconnect (1s→2s→4s→max 30s)
3. `src/hooks/useAnomalyStream.ts` — parses WS JSON, dispatches to Zustand stores
4. `src/stores/servicesStore.ts`, `incidentsStore.ts`, `metricsStore.ts`
5. `src/components/dashboard/{ServiceHealthGrid,AnomalyScoreChart,IncidentFeed,DependencyGraph,DriftAlertBanner}.tsx`
6. `src/components/copilot/CopilotChatPanel.tsx` — SSE streaming via `fetch()` + `ReadableStream`
7. Playwright E2E: verify WS connects and the score chart renders on a simulated anomaly event

WebSocket message contract: `anomaly_score`, `action_receipt`, `drift_alert` — agree the JSON
schema with `services/ml-backend`'s `app/api/websocket.py` before wiring this up (same person,
but keep the schema written down in `docs/API.md` once decided).
