import type { IncidentEntry, ServiceHealth } from "@/features/dashboard/types";
import type { ServiceRow } from "@/features/services/types";
import type { Severity } from "@/shared/types";
import type { ApiAnomaly, ApiInfra, ApiService } from "./api";

export interface LiveServiceData {
  services: ServiceHealth[];
  serviceRows: ServiceRow[];
  incidents: IncidentEntry[];
}

function toSeverity(health: string, score: number): Severity {
  if (health === "down" || health === "failing" || score >= 0.85)
    return "critical";
  if (score >= 0.7) return "degrade";
  if (score >= 0.5) return "warn";
  if (health === "degraded") return "warn";
  return "watch";
}

export function mapLiveServiceData(
  services: ApiService[],
  infra: ApiInfra[],
  anomalies: ApiAnomaly[],
): LiveServiceData {
  const infraById = new Map(infra.map((item) => [item.service_id, item]));
  const anomalyById = new Map(anomalies.map((item) => [item.service_id, item]));
  const healthById = new Map<string, ServiceHealth>();

  const serviceHealth = services.map((service) => {
    const anomaly = anomalyById.get(service.service_id);
    const anomalyScore = anomaly?.anomaly_score ?? 0;
    const mapped: ServiceHealth = {
      serviceId: service.service_id,
      displayName: service.display_name,
      status: toSeverity(service.health, anomalyScore),
      anomalyScore,
      scoreHistory: [anomalyScore],
      lastAction: null,
      lastActionAt: null,
      driftDetected: false,
    };
    healthById.set(service.service_id, mapped);
    return mapped;
  });

  const serviceRows = services.map((service) => {
    const health = healthById.get(service.service_id)!;
    const infraData = infraById.get(service.service_id);
    const totalReplicas = infraData?.pod_count ?? service.replicas;
    const readyReplicas = infraData?.ready_pods ?? totalReplicas;
    return {
      ...health,
      runtime: service.runtime,
      team: service.team,
      tier: service.tier,
      region: service.region,
      nodePool: service.node_pool,
      node: infraData?.node ?? "Unavailable",
      replicas: `${readyReplicas}/${totalReplicas}`,
    };
  });

  const incidents = anomalies.map((anomaly) => {
    const service = healthById.get(anomaly.service_id);
    return {
      id: anomaly.id,
      serviceId: anomaly.service_id,
      serviceName:
        anomaly.service_name || service?.displayName || anomaly.service_id,
      severity: service?.status ?? toSeverity("healthy", anomaly.anomaly_score),
      actionType: "Anomaly detected",
      executor: "anomaly-detector",
      timestamp: anomaly.detected_at,
      details: `${anomaly.metric}: ${anomaly.actual_value} (expected ${anomaly.expected_value})`,
    };
  });

  return { services: serviceHealth, serviceRows, incidents };
}
