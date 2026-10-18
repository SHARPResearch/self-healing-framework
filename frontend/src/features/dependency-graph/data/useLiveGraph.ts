import { useEffect, useState } from "react";
import type { Severity } from "@/shared/types";
import type { GraphEdge, GraphNodeInput, ServiceLayer } from "../types";
import {
  fetchGraph,
  fetchAnomalies,
  fetchInfra,
  fetchApp,
  fetchServices,
} from "@/lib/api";

// ─── API response shapes ────────────────────────────────────────────
interface ApiServiceMeta {
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

interface ApiNode {
  id: string;
  name: string;
  namespace: string;
  criticality: number;
  health: "healthy" | "degraded" | "down";
}
interface ApiEdge {
  source: string;
  target: string;
  strength: number;
  protocol: string;
}
interface ApiAnomaly {
  service_id: string;
  anomaly_score: number;
  severity: "low" | "medium" | "high";
  metric?: string;
  actual_value?: number;
  expected_value?: number;
}
export interface ApiInfra {
  service_id: string;
  pod_count: number;
  ready_pods: number;
  cpu: { usage_pct: number; cores_used: number };
  memory: { used_mb: number; limit_mb: number; pct: number };
  network: { rx_kbps: number; tx_kbps: number };
  restarts_last_5m: number;
  node: string;
}
export interface ApiApp {
  service_id: string;
  requests_per_sec: number;
  latency_ms: { p50: number; p95: number; p99: number };
  error_rate: number;
  status_codes: { "2xx": number; "4xx": number; "5xx": number };
  active_connections: number;
  db_query_p95_ms: number;
  cache_hit_rate: number;
}

// ─── Health -> Severity mapping ─────────────────────────────────────
function toSeverity(health: string, score: number): Severity {
  if (health === "down" || score >= 0.85) return "critical";
  if (health === "degraded" || score >= 0.7) return "warn";
  if (score >= 0.5) return "degrade";
  return "watch";
}

// ─── The hook ───────────────────────────────────────────────────────
export function useLiveGraph(pollMs = 3000) {
  const [nodes, setNodes] = useState<GraphNodeInput[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [infraByService, setInfraByService] = useState<Map<string, ApiInfra>>(
    new Map(),
  );
  const [appByService, setAppByService] = useState<Map<string, ApiApp>>(
    new Map(),
  );
  const [anomalyByService, setAnomalyByService] = useState<
    Map<string, ApiAnomaly>
  >(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const [graphData, anomalies, infra, app, services] = await Promise.all([
          fetchGraph(),
          fetchAnomalies(),
          fetchInfra(),
          fetchApp(),
          fetchServices(),
        ]);
        if (!alive) return;

        const aMap = new Map<string, ApiAnomaly>(
          (anomalies as ApiAnomaly[]).map((a) => [a.service_id, a]),
        );
        const iMap = new Map<string, ApiInfra>(
          (infra as ApiInfra[]).map((i) => [i.service_id, i]),
        );
        const pMap = new Map<string, ApiApp>(
          (app as ApiApp[]).map((a) => [a.service_id, a]),
        );
        const metaMap = new Map<string, ApiServiceMeta>(
          (services as ApiServiceMeta[]).map((s) => [s.service_id, s]),
        );

        const liveNodes: GraphNodeInput[] = (graphData.nodes as ApiNode[]).map(
          (n) => {
            const anomaly = aMap.get(n.id);
            const score = anomaly?.anomaly_score ?? 0;
            const meta = metaMap.get(n.id);

            return {
              serviceId: n.id,
              displayName: n.name,
              status: toSeverity(n.health, score),
              anomalyScore: score,
              lastAction: null,

              // ─── NEW ──────────────────────────────────────────
              layer: (meta?.layer as ServiceLayer) ?? "unknown",
              team: meta?.team,
              runtime: meta?.runtime,
              version: meta?.version,
              criticality: n.criticality ?? 0.5,
            };
          },
        );
        const liveEdges: GraphEdge[] = (graphData.edges as ApiEdge[]).map(
          (e) => {
            const appData = pMap.get(e.target);
            return {
              source: e.source,
              target: e.target,
              latencyMs: Math.round(appData?.latency_ms.p99 ?? 50),
            };
          },
        );

        setNodes(liveNodes);
        setEdges(liveEdges);
        setInfraByService(iMap);
        setAppByService(pMap);
        setAnomalyByService(aMap);
        setError(null);
        setLoading(false);
      } catch (err: any) {
        if (!alive) return;
        console.error("graph load error", err);
        setError(String(err.message ?? err));
        setLoading(false);
      }
    };

    load();
    const id = setInterval(load, pollMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [pollMs]);

  return {
    nodes,
    edges,
    infraByService,
    appByService,
    anomalyByService,
    loading,
    error,
  };
}
