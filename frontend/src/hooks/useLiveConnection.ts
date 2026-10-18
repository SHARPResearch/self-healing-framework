import { useEffect } from "react";
import { api, wsUrl } from "@/lib/mlBackend";
import type { LiveMessage } from "@/features/lifecycle/types";
import { toDecision, useLiveStore } from "@/shared/store/liveStore";
import { useNotificationStore } from "@/shared/store/notificationStore";
import type { AppNotification } from "@/features/notifications/types";
import type { Severity } from "@/shared/types";

/**
 * One app wide connection to services/ml-backend: native WebSocket on /ws/events with
 * exponential backoff (1s, 2s, 4s ... 30s), plus a light REST poll for the slower views (model
 * registry, dashboard summary, health). Every page renders its own AppShell, so the connection
 * lives at module level and the hook only makes sure it has started; navigating between pages
 * never reconnects.
 *
 * Score messages arrive at ~24/s across the demo fleet, so incoming messages are queued and applied
 * to the store in one batch every FLUSH_MS.
 */
const FLUSH_MS = 250;
const POLL_MS = 4000;
const MAX_BACKOFF_MS = 30_000;

let started = false;
let backoff = 1000;
let queue: LiveMessage[] = [];

async function refreshSlowViews(): Promise<void> {
  const store = useLiveStore.getState();
  const [health, models, summary] = await Promise.all([api.health(), api.models(), api.summary()]);
  store.setHealth(health);
  store.setModels(models);
  store.setSummary(summary);
}

async function bootstrap(): Promise<void> {
  const store = useLiveStore.getState();
  const [services, decisions, queries] = await Promise.all([
    api.services(),
    api.decisions(200),
    api.queries(),
  ]);
  store.setServices(services);
  store.setDecisions(decisions);
  store.setQueries(queries);
  await refreshSlowViews();
  await Promise.all(
    services.map((s) => api.scores(s.serviceId, 300).then((points) => store.setScores(s.serviceId, points))),
  );
}

const DECISION_SEVERITY: Record<string, Severity> = {
  promote: "watch",
  rollback: "warn",
  hold: "degrade",
  ask: "warn",
};

function notify(msg: LiveMessage): void {
  const store = useLiveStore.getState();
  const name = (msg.service_id && store.services[msg.service_id]?.displayName) || msg.service_id || "Fleet";
  let n: Omit<AppNotification, "id" | "read" | "timestamp" | "serviceId"> | null = null;
  if (msg.type === "lifecycle_decision") {
    const d = toDecision(msg.data);
    if (d.action in DECISION_SEVERITY && d.action !== "ask") {
      n = {
        kind: "drift",
        severity: DECISION_SEVERITY[d.action],
        title: `${name}: ${d.verdict.replace("_", " ")}, model ${d.action}`,
        body: d.reason,
      };
    }
  } else if (msg.type === "operator_query") {
    n = {
      kind: "drift",
      severity: "warn",
      title: `${name}: new normal or incident?`,
      body: String(msg.data.reason ?? "CADAL could not attribute a persistent shift and asks the operator."),
    };
  }
  if (!n) return;
  useNotificationStore.getState().add({
    ...n,
    id: `live-${msg.type}-${msg.ts}-${msg.service_id ?? ""}`,
    serviceId: msg.service_id ?? "",
    timestamp: msg.ts,
    read: false,
  });
}

function connect(): void {
  const store = useLiveStore.getState();
  store.setStatus(store.ready ? "reconnecting" : "connecting");
  let ws: WebSocket;
  try {
    ws = new WebSocket(wsUrl());
  } catch {
    scheduleReconnect();
    return;
  }
  ws.onopen = () => {
    backoff = 1000;
    useLiveStore.getState().setStatus("live");
    bootstrap().catch(() => undefined);
  };
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data as string) as LiveMessage;
      queue.push(msg);
      notify(msg);
    } catch {
      // ignore malformed frames
    }
  };
  ws.onerror = () => ws.close();
  ws.onclose = () => scheduleReconnect();
}

function scheduleReconnect(): void {
  const store = useLiveStore.getState();
  store.setStatus(store.ready ? "reconnecting" : "offline");
  window.setTimeout(connect, backoff);
  backoff = Math.min(backoff * 2, MAX_BACKOFF_MS);
}

function start(): void {
  if (started) return;
  started = true;
  connect();
  window.setInterval(() => {
    if (!queue.length) return;
    const batch = queue;
    queue = [];
    useLiveStore.getState().applyMessages(batch);
  }, FLUSH_MS);
  window.setInterval(() => {
    if (useLiveStore.getState().status === "live") refreshSlowViews().catch(() => undefined);
  }, POLL_MS);
}

export function useLiveConnection(): void {
  useEffect(start, []);
}

/** Re-fetch everything now, e.g. right after an operator action. */
export async function refreshLive(): Promise<void> {
  const store = useLiveStore.getState();
  const [decisions, queries] = await Promise.all([api.decisions(200), api.queries()]);
  store.setDecisions(decisions);
  store.setQueries(queries);
  await refreshSlowViews();
}
