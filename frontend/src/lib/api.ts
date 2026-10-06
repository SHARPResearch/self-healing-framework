const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok)
    throw new Error(`API request failed (${response.status}): ${path}`);
  return response.json() as Promise<T>;
}

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

export interface ApiAnomaly {
  id: string;
  service_id: string;
  service_name: string;
  anomaly_score: number;
  severity: "low" | "medium" | "high";
  metric: string;
  actual_value: number;
  expected_value: number;
  detected_at: string;
}

export interface ApiInfra {
  service_id: string;
  pod_count: number;
  ready_pods: number;
  node: string;
}

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

export async function fetchGraph(): Promise<ApiGraph> {
  return request<ApiGraph>("/api/graph/");
}

export async function fetchAnomalies(): Promise<ApiAnomaly[]> {
  return request<ApiAnomaly[]>("/api/anomalies/recent");
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
