import type { AppNotification } from "../types";

/**
 * Mock only. Service ids and actions line up with the dashboard's mock
 * services and incident feed so the whole app tells one consistent story.
 */
export const notifications: AppNotification[] = [
  {
    id: "ntf-1",
    kind: "incident",
    severity: "critical",
    title: "Payments Service went critical",
    body: "Anomaly score 0.91 crossed the critical threshold. Traffic drained to 0%.",
    serviceId: "service-e-payments",
    timestamp: "2026-08-16T06:05:00Z",
    read: false,
  },
  {
    id: "ntf-2",
    kind: "action",
    severity: "critical",
    title: "Restart and rollback dispatched",
    body: "KubernetesExecutor restarted the pod, MlflowRollbackExecutor reverted the model.",
    serviceId: "service-e-payments",
    timestamp: "2026-08-16T06:05:00Z",
    read: false,
  },
  {
    id: "ntf-3",
    kind: "drift",
    severity: "warn",
    title: "Model drift detected",
    body: "ADWIN flagged a distribution change. Candidate model promoted for review.",
    serviceId: "service-c-inventory",
    timestamp: "2026-08-16T04:08:00Z",
    read: false,
  },
  {
    id: "ntf-4",
    kind: "action",
    severity: "degrade",
    title: "Traffic shifted to 50%",
    body: "YarpTrafficShifter reduced the weight while an extra replica warms up.",
    serviceId: "service-b-orders",
    timestamp: "2026-08-15T05:42:00Z",
    read: true,
  },
  {
    id: "ntf-5",
    kind: "rca",
    severity: "critical",
    title: "Root cause summary ready",
    body: "Copilot drafted an RCA for the payments incident. Confidence: medium.",
    serviceId: "service-e-payments",
    timestamp: "2026-08-15T06:20:00Z",
    read: true,
  },
  {
    id: "ntf-6",
    kind: "anomaly",
    severity: "warn",
    title: "Anomaly score crossed 0.5",
    body: "Inventory Service entered the warn band. Pre warming a replica.",
    serviceId: "service-c-inventory",
    timestamp: "2026-08-15T03:55:00Z",
    read: true,
  },
  {
    id: "ntf-7",
    kind: "anomaly",
    severity: "watch",
    title: "Search Service back to baseline",
    body: "Anomaly score settled at 0.15 after the index rebuild.",
    serviceId: "service-f-search",
    timestamp: "2026-08-15T02:10:00Z",
    read: true,
  },
];
