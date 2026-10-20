const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok)
    throw new Error(`API request failed (${response.status}): ${path}`);
  return response.json() as Promise<T>;
}

// ─── Service catalog ───────────────────────────────────────────────
export interface ApiService {
  service_id: string;
  display_name: string;
  layer: "edge" | "bff" | "domain" | "data";
  team: string;
  tier: number;
  runtime: string;
  version: string;
  region: string;
  node_pool: string;
  replicas: number;
  health: string;
}

// ─── Anomaly (live, from mock) ─────────────────────────────────────
export interface ApiAnomaly {
  id: string;
  service_id: string;
  service_name?: string;
  anomaly_score: number;
  severity: "low" | "medium" | "high";
  metric?: string;
  actual_value?: number;
  expected_value?: number;
  detected_at: string;
  features?: Record<string, unknown>;
}

// ─── Anomaly (from DB) ─────────────────────────────────────────────
export interface ApiDbAnomaly {
  id: string;
  service_id: string;
  service_name: string | null;
  team: string | null;
  layer: string | null;
  anomaly_score: number;
  severity: "low" | "medium" | "high";
  metric: string | null;
  actual_value: number | null;
  expected_value: number | null;
  deviation_sigma: number | null;
  confidence: number | null;
  model_version: string | null;
  features: Record<string, unknown> | null;
  detected_at: string;
  snapshot_status: "pending" | "captured" | "failed";
  snapshot_from: string | null;
  snapshot_to: string | null;
  captured_at: string | null;
}

// ─── Evidence bundle ───────────────────────────────────────────────
export interface ApiInfraSnapshot {
  anomaly_id: string;
  time: string;
  service_id: string;
  cpu_usage_pct: number | null;
  mem_pct: number | null;
  mem_used_mb: number | null;
  mem_limit_mb: number | null;
  ready_pods: number | null;
  pod_count: number | null;
  restarts_last_5m: number | null;
  net_rx_kbps: number | null;
  net_tx_kbps: number | null;
}

export interface ApiAppSnapshot {
  anomaly_id: string;
  time: string;
  service_id: string;
  rps: number | null;
  latency_p50: number | null;
  latency_p90: number | null;
  latency_p95: number | null;
  latency_p99: number | null;
  error_rate: number | null;
  status_2xx: number | null;
  status_3xx: number | null;
  status_4xx: number | null;
  status_5xx: number | null;
  active_conns: number | null;
  queue_depth: number | null;
  db_p95_ms: number | null;
  cache_hit_rate: number | null;
}

export interface ApiEvidenceBundle {
  anomaly: ApiDbAnomaly;
  infra_snapshots: ApiInfraSnapshot[];
  app_snapshots: ApiAppSnapshot[];
  counts: { infra: number; app: number };
}

// ─── Live infra + app ──────────────────────────────────────────────
export interface ApiInfra {
  service_id: string;
  pod_count: number;
  ready_pods: number;
  node: string;
}

export interface ApiApp {
  service_id: string;
  requests_per_sec: number;
  latency_ms: { p50: number; p95: number; p99: number };
  error_rate: number;
}

// ─── Graph ─────────────────────────────────────────────────────────
export interface ApiGraph {
  nodes: Array<{
    id: string;
    name: string;
    namespace: string;
    criticality: number;
    health: string;
  }>;
  edges: Array<{
    source: string;
    target: string;
    strength: number;
    protocol: string;
  }>;
}

// ─── Decisions API ─────────────────────────────────────────────
export interface ApiDecision {
  decision_id: string;
  anomaly_id: string;
  service_id: string;
  rule_id: string | null;
  rule_version: number | null;
  action: string;
  action_params: Record<string, any>;
  confidence: {
    detection: number;
    rule: number;
    final: number;
  };
  severity: {
    base_severity: number;
    centrality: number;
    blast_factor: number;
    effective_severity: number;
    normalized: number;
    label: string;
  };
  base_risk: string;
  blast_factor: number;
  centrality: number;
  selection: {
    selected: any;
    rejected: any[];
    strategy: string;
    reason: string;
  };
  context: {
    service_health: string;
    anomaly_kind: string;
    upstream: string[];
    downstream: string[];
    blast_members: string[];
  };
  policy: {
    outcome: string | null;
    reason: string | null;
  };
  created_at: string;
}

export interface ApiDecisionsRecentResponse {
  count: number;
  decisions: ApiDecision[];
}

export async function fetchDecisions(limit = 50): Promise<ApiDecision[]> {
  const res = await fetch(`${API_BASE}/api/decisions/recent?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to fetch decisions: ${res.status}`);
  const data: ApiDecisionsRecentResponse = await res.json();
  return data.decisions;
}

export async function fetchDecision(decisionId: string): Promise<ApiDecision> {
  const res = await fetch(`${API_BASE}/api/decisions/${decisionId}`);
  if (!res.ok) throw new Error(`Failed to fetch decision: ${res.status}`);
  return res.json();
}

// ─── Rules API (Hybrid Rule Management) ────────────────────────────
export type RuleStatus = "DRAFT" | "ACTIVE" | "ARCHIVED";

export interface ApiRuleConditionLeaf {
  metric: string;
  op: ">" | ">=" | "<" | "<=" | "==" | "!=" | "in" | "not_in" | "contains";
  value: unknown;
}
export interface ApiRuleConditionAll {
  all: ApiRuleCondition[];
}
export interface ApiRuleConditionAny {
  any: ApiRuleCondition[];
}
export type ApiRuleCondition =
  | ApiRuleConditionLeaf
  | ApiRuleConditionAll
  | ApiRuleConditionAny;

export interface ApiRuleThen {
  action: string;
  params: Record<string, unknown>;
  base_confidence: number;
  base_risk: "LOW" | "MEDIUM" | "HIGH";
}

export interface ApiRuleGuardrails {
  cooldown_seconds: number;
  max_per_hour: number;
  idempotency_key: string | null;
}

export interface ApiRuleAppliesTo {
  layers: string[];
  services: string[];
  exclude_services: string[];
}

export interface ApiRule {
  id: string;
  version: number;
  priority: number;
  description: string;
  enabled: boolean;
  applies_to: ApiRuleAppliesTo;
  when: ApiRuleCondition;
  then: ApiRuleThen;
  guardrails: ApiRuleGuardrails;
  tags: string[];
  is_default: boolean;
  is_template: boolean;
  created_by: string;
  owner_org_id?: string | null;
  status: RuleStatus;
  parent_rule_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ApiRulesResponse {
  count: number;
  rules: ApiRule[];
}

export interface ApiRuleAuditEntry {
  id: number;
  rule_id: string;
  action: "CREATE" | "UPDATE" | "DELETE" | "TOGGLE" | "RELOAD";
  actor: string;
  diff: Record<string, unknown> | null;
  created_at: string;
}

export interface ApiRuleValidateResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  rule: ApiRule | null;
  match_preview?: {
    total_anomalies: number;
    eligible_anomalies?: number;
    matched_count: number;
    matched_anomaly_ids?: string[];
    evaluation_errors?: number;
    message: string;
  };
}

export type RuleListFilter =
  | "all"
  | "default"
  | "custom"
  | "templates"
  | "archived";

async function ruleRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let detail = `API request failed (${response.status}): ${path}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (body?.detail?.message)
        detail = `${body.detail.message}: ${(body.detail.errors ?? []).join("; ")}`;
    } catch {
      /* keep the default message */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function fetchRules(filter: RuleListFilter = "all"): Promise<ApiRule[]> {
  const qs = filter === "all" ? "" : `?type=${filter}`;
  const data = await ruleRequest<ApiRulesResponse>(`/api/rules${qs}`);
  return data.rules;
}

export async function fetchRule(ruleId: string): Promise<ApiRule> {
  return ruleRequest<ApiRule>(`/api/rules/${encodeURIComponent(ruleId)}`);
}

export async function toggleRule(
  ruleId: string,
  enabled?: boolean,
  actor = "admin",
): Promise<{ ok: boolean; enabled: boolean; rule: ApiRule }> {
  const qs = enabled === undefined ? "" : `?enabled=${enabled}`;
  return ruleRequest(`/api/rules/${encodeURIComponent(ruleId)}/toggle${qs}`, {
    method: "POST",
    headers: { "X-Actor": actor },
  });
}

export async function patchRule(
  ruleId: string,
  patch: Partial<{
    priority: number;
    when: ApiRuleCondition;
    applies_to: ApiRuleAppliesTo;
    guardrails: ApiRuleGuardrails;
    enabled: boolean;
    description: string;
    status: RuleStatus;
    tags: string[];
  }>,
  actor = "admin",
): Promise<{ ok: boolean; changed: string[]; rule: ApiRule }> {
  return ruleRequest(`/api/rules/${encodeURIComponent(ruleId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify(patch),
  });
}

export async function createCustomRule(
  payload: Partial<ApiRule> & {
    id: string;
    description: string;
    when: ApiRuleCondition;
    then: ApiRuleThen;
  },
  actor = "user",
): Promise<{ ok: boolean; rule: ApiRule; warnings: string[] }> {
  return ruleRequest(`/api/rules/custom`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify(payload),
  });
}

export async function deleteRule(ruleId: string, actor = "admin"): Promise<void> {
  await ruleRequest(`/api/rules/${encodeURIComponent(ruleId)}`, {
    method: "DELETE",
    headers: { "X-Actor": actor },
  });
}

export async function validateRule(
  ruleId: string,
  payload: Record<string, unknown>,
  test = false,
  actor = "user",
): Promise<ApiRuleValidateResult> {
  const qs = test ? "?test=true" : "";
  return ruleRequest(`/api/rules/${encodeURIComponent(ruleId)}/validate${qs}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Actor": actor },
    body: JSON.stringify(payload),
  });
}

export async function fetchRuleAudit(ruleId: string): Promise<ApiRuleAuditEntry[]> {
  const data = await ruleRequest<{ rule_id: string; count: number; entries: ApiRuleAuditEntry[] }>(
    `/api/rules/${encodeURIComponent(ruleId)}/audit`,
  );
  return data.entries;
}

export async function fetchRuleTemplates(): Promise<ApiRule[]> {
  const data = await ruleRequest<ApiRulesResponse>(`/api/rules/templates`);
  return data.rules;
}

// ─── API functions ─────────────────────────────────────────────────
export async function fetchGraph(): Promise<ApiGraph> {
  return request<ApiGraph>("/api/graph/");
}

export async function fetchAnomalies(): Promise<ApiAnomaly[]> {
  return request<ApiAnomaly[]>("/api/anomalies/recent");
}

/** Anomalies from the DB with snapshot_status — used by /anomalies page */
export async function fetchDbAnomalies(limit = 100): Promise<ApiDbAnomaly[]> {
  return request<ApiDbAnomaly[]>(`/api/anomalies/recent?limit=${limit}`);
}

/** Full evidence bundle: anomaly + all infra/app snapshots */
export async function fetchAnomalyEvidence(
  anomalyId: string,
): Promise<ApiEvidenceBundle> {
  return request<ApiEvidenceBundle>(
    `/api/anomalies/${encodeURIComponent(anomalyId)}/evidence`,
  );
}

export async function fetchInfra(): Promise<ApiInfra[]> {
  return request<ApiInfra[]>("/api/infra");
}

export async function fetchApp<T = unknown>(): Promise<T> {
  return request<T>("/api/app");
}

export async function fetchServices(): Promise<ApiService[]> {
  return request<ApiService[]>("/api/services");
}

export async function runScenario<
  T = { scenario: string; health: Record<string, string> },
>(name: string): Promise<T> {
  return request<T>(`/api/mock/scenario/${encodeURIComponent(name)}`, {
    method: "POST",
  });
}

export const API_URL = API_BASE;
