import type {
  BackendHealth,
  DashboardSummary,
  InjectionKind,
  LifecycleDecision,
  LiveServiceHealth,
  OperatorQuery,
  QueryAnswer,
  ScorePoint,
} from "@/features/lifecycle/types";
import type { ModelDetail, ModelRun } from "@/features/models/types";

/**
 * Typed client for services/ml-backend. Same origin by default (Vite proxies /api and /ws to
 * :8002, the ml-backend, in dev); VITE_ML_BACKEND_URL points it somewhere else. lib/api.ts is a
 * separate client for the decision engine (:8000).
 */
const API_BASE = (import.meta.env.VITE_ML_BACKEND_URL as string | undefined)?.replace(/\/$/, "") ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body: unknown = {}) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export function wsUrl(path = "/ws/events"): string {
  if (API_BASE) return API_BASE.replace(/^http/, "ws") + path;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}

export interface ActionResult {
  decision: LifecycleDecision;
  model: ModelRun;
}

export const api = {
  health: () => request<BackendHealth>("/health"),
  services: () => request<LiveServiceHealth[]>("/services"),
  scores: (serviceId: string, limit = 300) =>
    request<ScorePoint[]>(`/services/${serviceId}/scores?limit=${limit}`),
  summary: () => request<DashboardSummary>("/dashboard/summary"),
  models: () => request<ModelRun[]>("/models"),
  model: (serviceId: string) => request<ModelDetail>(`/models/${serviceId}`),
  promote: (serviceId: string, operator: string, version?: number) =>
    post<ActionResult>(`/models/${serviceId}/promote`, { operator, version }),
  rollback: (serviceId: string, operator: string, version?: number) =>
    post<ActionResult>(`/models/${serviceId}/rollback`, { operator, version }),
  validityCheck: (serviceId: string) => post<{ phase: string }>(`/models/${serviceId}/validity-check`),
  decisions: (limit = 100) => request<LifecycleDecision[]>(`/lifecycle/decisions?limit=${limit}`),
  queries: (status?: string) => request<OperatorQuery[]>(`/queries${status ? `?status=${status}` : ""}`),
  answer: (queryId: string, answer: QueryAnswer, operator: string) =>
    post<ActionResult>(`/queries/${queryId}/answer`, { answer, operator }),
  inject: (serviceId: string, kind: InjectionKind) => post<Record<string, unknown>>(`/demo/${serviceId}/${kind}`),
  speed: (body: { eventsPerSec?: number; paused?: boolean }) =>
    post<{ eventsPerSec: number; paused: boolean }>("/demo/speed", body),
  reset: () => post<{ status: string }>("/demo/reset"),
};
