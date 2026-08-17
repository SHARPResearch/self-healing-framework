import { services } from "@/features/dashboard/data/mockData";
import type { ActivityLogEntry, ServiceMetadata, ServiceRow } from "../types";

/**
 * Mock data only -- no k8s API wired up yet. Runtimes match
 * services/target-services/'s documented Node/Python/Go stack.
 */
export const serviceMetadataById: Record<string, ServiceMetadata> = {
  "service-a-auth": {
    serviceId: "service-a-auth",
    runtime: "node",
    namespace: "production",
    clusterIp: "10.96.10.11",
    replicas: "3/3",
  },
  "service-b-orders": {
    serviceId: "service-b-orders",
    runtime: "go",
    namespace: "production",
    clusterIp: "10.96.10.22",
    replicas: "3/3",
  },
  "service-c-inventory": {
    serviceId: "service-c-inventory",
    runtime: "python",
    namespace: "production",
    clusterIp: "10.96.10.33",
    replicas: "4/4",
  },
  "service-d-notification": {
    serviceId: "service-d-notification",
    runtime: "node",
    namespace: "production",
    clusterIp: "10.96.10.44",
    replicas: "2/2",
  },
  "service-e-payments": {
    serviceId: "service-e-payments",
    runtime: "go",
    namespace: "production",
    clusterIp: "10.96.10.55",
    replicas: "2/3",
  },
  "service-f-search": {
    serviceId: "service-f-search",
    runtime: "python",
    namespace: "production",
    clusterIp: "10.96.10.66",
    replicas: "3/3",
  },
};

export const activityLogByService: Record<string, ActivityLogEntry[]> = {
  "service-a-auth": [
    { id: "log-a-1", message: "Health check passed", timestamp: "2026-08-16T05:58:00Z" },
    { id: "log-a-2", message: "Anomaly score steady at 0.12", timestamp: "2026-08-16T05:48:00Z" },
  ],
  "service-b-orders": [
    { id: "log-b-1", message: "Traffic shifted 50% to canary", timestamp: "2026-08-15T05:42:00Z" },
    { id: "log-b-2", message: "Anomaly score crossed 0.7 (degrade)", timestamp: "2026-08-15T05:38:00Z" },
  ],
  "service-c-inventory": [
    { id: "log-c-1", message: "Scaled 3 -> 4 replicas", timestamp: "2026-08-15T04:10:00Z" },
    { id: "log-c-2", message: "ADWIN drift detected", timestamp: "2026-08-15T04:08:00Z" },
  ],
  "service-d-notification": [
    { id: "log-d-1", message: "Health check passed", timestamp: "2026-08-16T05:55:00Z" },
  ],
  "service-e-payments": [
    { id: "log-e-1", message: "Restarted and rolled back to previous revision", timestamp: "2026-08-15T06:05:00Z" },
    { id: "log-e-2", message: "Anomaly score crossed 0.85 (critical)", timestamp: "2026-08-15T06:03:00Z" },
  ],
  "service-f-search": [
    { id: "log-f-1", message: "Health check passed", timestamp: "2026-08-16T05:50:00Z" },
  ],
};

export const serviceRows: ServiceRow[] = services.map((service) => ({
  ...service,
  ...serviceMetadataById[service.serviceId],
}));
