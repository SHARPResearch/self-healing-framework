import { create } from "zustand";
import type {
  BackendHealth,
  DashboardSummary,
  LifecycleDecision,
  LifecyclePhase,
  LiveMessage,
  LiveServiceHealth,
  OperatorQuery,
  QuarantineProgress,
  ScorePoint,
} from "@/features/lifecycle/types";
import type { ModelRun } from "@/features/models/types";
import type { Severity } from "@/shared/types";

/**
 * Live state from services/ml-backend, fed by GET /ws/events and a few REST polls (see
 * hooks/useLiveConnection.ts). `ready` turns true after the first snapshot and stays true across
 * reconnects, so a network blip mid demo keeps showing the last live data instead of flipping
 * back to mock data. Pages read mock data only while `ready` is false.
 */
export type ConnectionStatus = "connecting" | "live" | "reconnecting" | "offline";

export type FeedKind =
  | "quarantine"
  | "change"
  | "decision"
  | "query"
  | "answer"
  | "expired"
  | "transition"
  | "injection";

export interface FeedEntry {
  id: string;
  kind: FeedKind;
  serviceId: string | null;
  ts: string;
  title: string;
  detail: string;
  tone: "neutral" | "info" | "good" | "warn" | "bad";
}

const SCORE_BUFFER = 300;
const MAX_DECISIONS = 200;
const MAX_FEED = 120;

interface LiveState {
  status: ConnectionStatus;
  ready: boolean;
  health: BackendHealth | null;
  serviceOrder: string[];
  services: Record<string, LiveServiceHealth>;
  scores: Record<string, ScorePoint[]>;
  models: Record<string, ModelRun>;
  decisions: LifecycleDecision[];
  queries: Record<string, OperatorQuery>;
  summary: DashboardSummary | null;
  feed: FeedEntry[];
  operator: string;

  setStatus: (status: ConnectionStatus) => void;
  setHealth: (health: BackendHealth | null) => void;
  setServices: (services: LiveServiceHealth[]) => void;
  setScores: (serviceId: string, points: ScorePoint[]) => void;
  setModels: (models: ModelRun[]) => void;
  upsertModel: (model: ModelRun) => void;
  setDecisions: (decisions: LifecycleDecision[]) => void;
  setQueries: (queries: OperatorQuery[]) => void;
  setSummary: (summary: DashboardSummary) => void;
  applyMessages: (messages: LiveMessage[]) => void;
  setOperator: (name: string) => void;
}

type Raw = Record<string, unknown>;

export function toDecision(d: Raw): LifecycleDecision {
  return {
    serviceId: String(d.service_id ?? d.serviceId ?? ""),
    step: (d.step as number) ?? null,
    version: (d.version as number) ?? null,
    action: d.action as LifecycleDecision["action"],
    verdict: d.verdict as LifecycleDecision["verdict"],
    trigger: String(d.trigger ?? ""),
    reason: String(d.reason ?? ""),
    evidence: (d.evidence as Raw) ?? {},
    queryId: (d.query_id as string) ?? (d.queryId as string) ?? null,
  };
}

function toQuery(q: Raw, serviceName: string, currentStep: number): OperatorQuery {
  return {
    queryId: String(q.query_id),
    serviceId: String(q.service_id),
    serviceName,
    status: q.status as OperatorQuery["status"],
    question: String(q.question ?? ""),
    reason: String(q.reason ?? ""),
    evidence: (q.evidence as Raw) ?? {},
    createdStep: Number(q.created_step ?? 0),
    expiresStep: Number(q.expires_step ?? 0),
    currentStep,
    answer: (q.answer as OperatorQuery["answer"]) ?? null,
    operator: (q.operator as string) ?? null,
  };
}

function sampleHistory(points: ScorePoint[], n = 20): number[] {
  if (points.length <= n) return points.map((p) => p.score);
  const out: number[] = [];
  for (let i = 0; i < n; i++) out.push(points[Math.round((i * (points.length - 1)) / (n - 1))].score);
  return out;
}

const ACTION_TONE: Record<string, FeedEntry["tone"]> = {
  promote: "good",
  rollback: "warn",
  hold: "bad",
  resume: "neutral",
  ask: "info",
};

const OPERATOR_KEY = "sharp.operator";

/** The name recorded in the audit trail for operator answers and manual actions (per browser). */
function readOperator(): string {
  try {
    return localStorage.getItem(OPERATOR_KEY) || "operator";
  } catch {
    return "operator";
  }
}

/** Mirrors the backend's views.drift_detected: a scheduled validity check is not drift. */
function isDrift(trigger: string | null, openQueries: number): boolean {
  return (trigger !== null && trigger !== "scheduled") || openQueries > 0;
}

let feedSeq = 0;
function feed(kind: FeedKind, msg: LiveMessage, title: string, detail: string, tone: FeedEntry["tone"]): FeedEntry {
  feedSeq += 1;
  return { id: `${msg.ts}-${feedSeq}`, kind, serviceId: msg.service_id, ts: msg.ts, title, detail, tone };
}

export const useLiveStore = create<LiveState>((set) => ({
  status: "connecting",
  ready: false,
  health: null,
  serviceOrder: [],
  services: {},
  scores: {},
  models: {},
  decisions: [],
  queries: {},
  summary: null,
  feed: [],
  operator: readOperator(),

  setStatus: (status) => set({ status }),
  setHealth: (health) => set({ health }),
  setServices: (services) =>
    set((state) => ({
      ready: true,
      serviceOrder: services.map((s) => s.serviceId),
      services: Object.fromEntries(
        services.map((s) => {
          const prev = state.scores[s.serviceId];
          return [s.serviceId, prev?.length ? { ...s, scoreHistory: sampleHistory(prev) } : s];
        }),
      ),
    })),
  setScores: (serviceId, points) =>
    set((state) => {
      const svc = state.services[serviceId];
      return {
        scores: { ...state.scores, [serviceId]: points.slice(-SCORE_BUFFER) },
        services: svc
          ? { ...state.services, [serviceId]: { ...svc, scoreHistory: sampleHistory(points) } }
          : state.services,
      };
    }),
  setModels: (models) => set({ models: Object.fromEntries(models.map((m) => [m.entityId, m])) }),
  upsertModel: (model) => set((state) => ({ models: { ...state.models, [model.entityId]: model } })),
  setDecisions: (decisions) => set({ decisions: decisions.slice(0, MAX_DECISIONS) }),
  setQueries: (queries) => set({ queries: Object.fromEntries(queries.map((q) => [q.queryId, q])) }),
  setSummary: (summary) => set({ summary }),
  setOperator: (operator) => {
    try {
      localStorage.setItem(OPERATOR_KEY, operator);
    } catch {
      // storage unavailable: keep it for this session only
    }
    set({ operator });
  },

  applyMessages: (messages) =>
    set((state) => {
      let services = state.services;
      let scores = state.scores;
      let decisions = state.decisions;
      let queries = state.queries;
      let serviceOrder = state.serviceOrder;
      let ready = state.ready;
      const newFeed: FeedEntry[] = [];
      const touchedScores = new Set<string>();

      const name = (sid: string | null) => (sid && services[sid]?.displayName) || sid || "fleet";
      const patch = (sid: string, fields: Partial<LiveServiceHealth>) => {
        const svc = services[sid];
        if (!svc) return;
        if (services === state.services) services = { ...services };
        services[sid] = { ...svc, ...fields };
      };

      for (const msg of messages) {
        const d = msg.data as Raw;
        const sid = msg.service_id;
        switch (msg.type) {
          case "snapshot": {
            const list = d.services as LiveServiceHealth[];
            services = Object.fromEntries(list.map((s) => [s.serviceId, s]));
            serviceOrder = list.map((s) => s.serviceId);
            queries = { ...queries };
            for (const q of d.queries as OperatorQuery[]) queries[q.queryId] = q;
            ready = true;
            break;
          }
          case "anomaly_score": {
            if (!sid) break;
            const point = { step: Number(d.step), score: Number(d.score), alarm: Boolean(d.alarm) };
            if (scores === state.scores) scores = { ...scores };
            // copy the buffer the first time this batch touches it, then append in place
            const current = scores[sid] ?? [];
            const buf = current === state.scores[sid] ? [...current] : current;
            const last = buf.at(-1);
            if (last && point.step <= last.step && point.step > last.step - SCORE_BUFFER * 10) break;
            buf.push(point);
            if (buf.length > SCORE_BUFFER) buf.splice(0, buf.length - SCORE_BUFFER);
            scores[sid] = buf;
            touchedScores.add(sid);
            const trigger = (d.trigger as string | null) ?? null;
            patch(sid, {
              anomalyScore: point.score,
              status: d.severity as Severity,
              alarm: point.alarm,
              modelVersion: Number(d.version),
              phase: d.phase as LifecyclePhase,
              quarantineTrigger: trigger,
              quarantine: (d.quarantine as QuarantineProgress | null | undefined) ?? null,
              driftDetected: isDrift(trigger, services[sid]?.openQueries ?? 0),
            });
            break;
          }
          case "quarantine_look":
            newFeed.push(
              feed("quarantine", msg,
                `${name(sid)}: early look at ${String(d.seen)} of ${String(d.length)} events`,
                d.conclusive
                  ? `Conclusive (${String(d.verdict).replace("_", " ")}): deciding now instead of waiting the full quarantine.`
                  : "Not conclusive yet; the quarantine continues.",
                d.conclusive ? "good" : "neutral"),
            );
            break;
          case "quarantine_opened": {
            const trigger = String(d.trigger);
            if (sid)
              patch(sid, {
                phase: "quarantine",
                quarantineTrigger: trigger,
                driftDetected: isDrift(trigger, services[sid]?.openQueries ?? 0),
              });
            newFeed.push(
              feed("quarantine", msg,
                trigger === "scheduled" ? `${name(sid)}: scheduled validity check` : `${name(sid)}: quarantine opened`,
                `Trigger ${String(d.trigger)}; observing ${String(d.length)} events while the champion keeps serving.`,
                trigger === "scheduled" ? "neutral" : "info"),
            );
            break;
          }
          case "change_observed":
            newFeed.push(
              feed("change", msg, `${name(sid)}: deployment observed`,
                `Change event ${String(d.change_event_id)} reached the lifecycle.`, "neutral"),
            );
            break;
          case "lifecycle_decision": {
            const dec = toDecision(d);
            decisions = [dec, ...decisions].slice(0, MAX_DECISIONS);
            newFeed.push(
              feed("decision", msg, `${name(sid)}: ${dec.verdict.replace("_", " ")} → ${dec.action}`,
                dec.reason, ACTION_TONE[dec.action] ?? "neutral"),
            );
            break;
          }
          case "operator_query":
          case "query_answered":
          case "query_expired": {
            const svcStep = sid ? (scores[sid]?.at(-1)?.step ?? 0) : 0;
            const q = toQuery(d, name(String(d.service_id ?? sid)), svcStep);
            queries = { ...queries, [q.queryId]: q };
            const openCount = Object.values(queries).filter(
              (x) => x.serviceId === q.serviceId && x.status === "open",
            ).length;
            patch(q.serviceId, {
              openQueries: openCount,
              driftDetected: isDrift(services[q.serviceId]?.quarantineTrigger ?? null, openCount),
            });
            if (msg.type === "operator_query")
              newFeed.push(feed("query", msg, `${q.serviceName}: CADAL asks the operator`, q.reason, "info"));
            else if (msg.type === "query_answered")
              newFeed.push(
                feed("answer", msg, `${q.serviceName}: operator ${q.operator ?? ""} answered`,
                  q.answer === "new_normal" ? "New normal: the validated candidate is promoted." : "Incident: the champion is kept.",
                  q.answer === "new_normal" ? "good" : "bad"),
              );
            else newFeed.push(feed("expired", msg, `${q.serviceName}: query expired`, "No answer in time, held safely.", "warn"));
            break;
          }
          case "model_transition": {
            const t = String(d.transition);
            if (t === "promote" || t === "rollback") {
              if (sid) patch(sid, { modelVersion: Number(d.to_version), lastAction: `Model ${t} to v${String(d.to_version)}`, lastActionAt: msg.ts });
              newFeed.push(
                feed("transition", msg, `${name(sid)}: model ${t} v${String(d.from_version)} → v${String(d.to_version)}`,
                  String(d.reason ?? ""), t === "promote" ? "good" : "warn"),
              );
            }
            break;
          }
          case "demo_injection":
            newFeed.push(
              feed("injection", msg, `${name(sid)}: injected ${String(d.kind).replace("_", " ")}`,
                `Demo injection on ${(d.features as string[] | undefined)?.length ?? 0} metrics.`, "neutral"),
            );
            break;
          case "demo_reset":
            decisions = [];
            queries = {};
            scores = {};
            newFeed.push(feed("injection", msg, "Demo reset", "Every service was rebuilt from its warm-up.", "neutral"));
            break;
        }
      }

      for (const sid of touchedScores) {
        const svc = services[sid];
        if (svc) services[sid] = { ...svc, scoreHistory: sampleHistory(scores[sid]) };
      }

      return {
        ready,
        services,
        serviceOrder,
        scores,
        decisions,
        queries,
        feed: newFeed.length ? [...newFeed.reverse(), ...state.feed].slice(0, MAX_FEED) : state.feed,
      };
    }),
}));

export function selectServices(state: LiveState): LiveServiceHealth[] {
  return state.serviceOrder.map((id) => state.services[id]).filter(Boolean);
}

export function selectOpenQueries(state: LiveState): OperatorQuery[] {
  return Object.values(state.queries).filter((q) => q.status === "open");
}
