import type { ServiceMetadata } from "../types";

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
