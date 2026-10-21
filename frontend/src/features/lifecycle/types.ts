import type { ServiceHealth } from "@/features/dashboard/types";

/**
 * JSON shapes served by services/ml-backend (see its README for the full REST and WebSocket
 * contract). The lifecycle is CADAL: a drift, change or schedule trigger opens a quarantine,
 * label free attribution reaches a verdict, and the verdict maps to an action. When the verdict
 * is ambiguous, CADAL asks the operator instead of guessing.
 */
export type LifecyclePhase = "stable" | "quarantine" | "deciding";

// "operator" marks a manual promote/rollback; the naive_rollback baseline uses "unattributed".
export type Verdict =
  | "incident"
  | "concept_drift"
  | "model_decay"
  | "no_change"
  | "ambiguous"
  | "operator"
  | "unattributed"
  | "scheduled";

export type LifecycleAction = "hold" | "promote" | "rollback" | "resume" | "ask";

export type QueryAnswer = "new_normal" | "incident";

export type QueryStatus = "open" | "answered" | "expired";

export type InjectionKind = "deploy" | "silent_change" | "incident";

/** Real scenarios on the live cluster (POST /api/live/{service}/{action}). */
export type LiveAction =
  | "rollout"
  | "traffic_up"
  | "traffic_reset"
  | "cpu_stress"
  | "memory_stress"
  | "pod_kill"
  | "network_delay";

export interface LiveServiceHealth extends ServiceHealth {
  phase: LifecyclePhase;
  /** What opened the current quarantine; "scheduled" is a routine validity check, not drift. */
  quarantineTrigger: string | null;
  alarm: boolean;
  modelVersion: number;
  openQueries: number;
  /** Where the service's telemetry comes from: an SMD machine (replay) or namespace/deployment (live). */
  smdEntity: string;
  source?: string;
}

export interface LifecycleDecision {
  serviceId: string;
  step: number | null;
  version: number | null;
  action: LifecycleAction;
  verdict: Verdict;
  trigger: string;
  reason: string;
  evidence: Record<string, unknown>;
  queryId: string | null;
}

export interface OperatorQuery {
  queryId: string;
  serviceId: string;
  serviceName: string;
  status: QueryStatus;
  question: string;
  reason: string;
  evidence: Record<string, unknown>;
  createdStep: number;
  expiresStep: number;
  currentStep: number;
  answer: QueryAnswer | null;
  operator: string | null;
}

export interface ModelVersionInfo {
  version: number;
  status: "production" | "candidate" | "archived" | string;
  stage: string;
  threshold: number;
  createdStep: number;
  kind: string | null;
  verdict: string | null;
  reason: string;
  queryId: string | null;
  operator: string | null;
  rebaselined: Record<string, number>;
}

export interface ModelTransition {
  seq: number;
  step: number;
  transition: "register" | "promote" | "rollback" | "checkpoint" | string;
  fromVersion: number | null;
  toVersion: number | null;
  reason: string;
  evidence: Record<string, unknown>;
  time: string;
}

export interface ScorePoint {
  step: number;
  score: number;
  alarm: boolean;
}

export interface DashboardSummary {
  activeAlarms: number;
  servicesInQuarantine: number;
  openQueries: number;
  modelUpdates: number;
  decisions: number;
  anomalyTrend: { label: string; score: number }[];
  counts: Record<string, number>;
}

export interface BackendHealth {
  status: string;
  /** "replay": SMD windows replayed; "prometheus": the live Online Boutique on Kubernetes. */
  mode?: "replay" | "prometheus";
  watcher?: boolean;
  liveActions?: boolean;
  namespace?: string | null;
  scrapeSeconds?: number | null;
  lifecycleDayMinutes?: number | null;
  store: "timescaledb" | "memory";
  db: boolean;
  redis: boolean;
  services: number;
  tick: number;
  eventsPerSec: number;
  paused: boolean;
  uptimeS: number;
}

/** WebSocket envelope, GET /ws/events. */
export interface LiveMessage<T = Record<string, unknown>> {
  type: string;
  service_id: string | null;
  ts: string;
  data: T;
}
