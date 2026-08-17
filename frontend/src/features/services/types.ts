import type { ServiceHealth } from "@/features/dashboard/types";

export type Runtime = "node" | "python" | "go";

/**
 * Static service-registry data (namespace, runtime, replicas) that would come
 * from the k8s API/service catalog in a real deployment -- a different source
 * than the live telemetry in ServiceHealth (dashboard/types.ts), joined by
 * serviceId. See data/mockData.ts.
 */
export interface ServiceMetadata {
  serviceId: string;
  runtime: Runtime;
  namespace: string;
  clusterIp: string;
  replicas: string;
}

export interface ActivityLogEntry {
  id: string;
  message: string;
  timestamp: string;
}

/** The table row shape: live telemetry joined with registry metadata. */
export type ServiceRow = ServiceHealth & ServiceMetadata;
