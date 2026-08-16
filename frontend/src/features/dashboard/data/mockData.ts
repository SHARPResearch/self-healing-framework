import type {
  AnomalyTrendPoint,
  DailyMetricPoint,
  IncidentEntry,
  ServiceHealth,
  StatCardData,
} from "../types";

/**
 * Mock data only -- no backend exists yet. Service names match
 * services/target-services/ (service-a-auth, service-b-orders,
 * service-c-inventory) plus the service-d-notification example already used in
 * docs/Doc3_Execution_Guide.md's dependency-annotation walkthrough, extended
 * with two plausible services for a fuller grid.
 */

export const statCards: StatCardData[] = [
  {
    label: "Active services",
    value: "24",
    deltaLabel: "3.1% vs last week",
    deltaDirection: "up",
    deltaTone: "positive",
  },
  {
    label: "Critical incidents",
    value: "3",
    deltaLabel: "12.4% vs last week",
    deltaDirection: "up",
    deltaTone: "negative",
  },
  {
    label: "Mean anomaly score",
    value: "0.34",
    deltaLabel: "0.4% vs last week",
    deltaDirection: "down",
    deltaTone: "positive",
  },
  {
    label: "Recovery actions today",
    value: "18",
    deltaLabel: "8.7% vs last week",
    deltaDirection: "up",
    deltaTone: "positive",
  },
];

export const recoveryActionsByDay: DailyMetricPoint[] = [
  { label: "Mon", value: 12 },
  { label: "Tue", value: 9 },
  { label: "Wed", value: 15 },
  { label: "Thu", value: 21 },
  { label: "Fri", value: 24 },
  { label: "Sat", value: 17 },
  { label: "Sun", value: 18 },
];

export const anomalyScoreTrend: AnomalyTrendPoint[] = [
  { label: "Apr 7", score: 0.18 },
  { label: "Apr 8", score: 0.22 },
  { label: "Apr 9", score: 0.31 },
  { label: "Apr 10", score: 0.44 },
  { label: "Apr 11", score: 0.29 },
  { label: "Apr 12", score: 0.52 },
  { label: "Apr 13", score: 0.34 },
];

export const services: ServiceHealth[] = [
  {
    serviceId: "service-a-auth",
    displayName: "Auth Service",
    status: "watch",
    anomalyScore: 0.12,
    scoreHistory: [0.1, 0.11, 0.09, 0.13, 0.12, 0.1, 0.12],
    lastAction: null,
    lastActionAt: null,
    driftDetected: false,
  },
  {
    serviceId: "service-b-orders",
    displayName: "Orders Service",
    status: "degrade",
    anomalyScore: 0.78,
    scoreHistory: [0.3, 0.42, 0.55, 0.61, 0.7, 0.74, 0.78],
    lastAction: "Traffic shifted 50%",
    lastActionAt: "2026-08-15T05:42:00Z",
    driftDetected: false,
  },
  {
    serviceId: "service-c-inventory",
    displayName: "Inventory Service",
    status: "warn",
    anomalyScore: 0.58,
    scoreHistory: [0.2, 0.25, 0.31, 0.4, 0.47, 0.52, 0.58],
    lastAction: "Scaled +1 replica",
    lastActionAt: "2026-08-15T04:10:00Z",
    driftDetected: true,
  },
  {
    serviceId: "service-d-notification",
    displayName: "Notification Service",
    status: "watch",
    anomalyScore: 0.08,
    scoreHistory: [0.09, 0.08, 0.07, 0.1, 0.08, 0.07, 0.08],
    lastAction: null,
    lastActionAt: null,
    driftDetected: false,
  },
  {
    serviceId: "service-e-payments",
    displayName: "Payments Service",
    status: "critical",
    anomalyScore: 0.91,
    scoreHistory: [0.4, 0.5, 0.62, 0.7, 0.81, 0.88, 0.91],
    lastAction: "Restarted + rolled back",
    lastActionAt: "2026-08-15T06:05:00Z",
    driftDetected: true,
  },
  {
    serviceId: "service-f-search",
    displayName: "Search Service",
    status: "watch",
    anomalyScore: 0.15,
    scoreHistory: [0.14, 0.16, 0.13, 0.15, 0.17, 0.14, 0.15],
    lastAction: null,
    lastActionAt: null,
    driftDetected: false,
  },
];

export const recentIncidents: IncidentEntry[] = [
  {
    id: "inc-1",
    serviceId: "service-e-payments",
    serviceName: "Payments Service",
    severity: "critical",
    actionType: "Restart + rollback",
    executor: "decision-engine",
    timestamp: "2026-08-15T06:05:00Z",
    details: "Anomaly score 0.91 exceeded critical threshold, traffic drained to 0%",
  },
  {
    id: "inc-2",
    serviceId: "service-b-orders",
    serviceName: "Orders Service",
    severity: "degrade",
    actionType: "Traffic shift 50%",
    executor: "yarp-gateway",
    timestamp: "2026-08-15T05:42:00Z",
    details: "Anomaly score 0.78, degrading traffic weight while scaling up",
  },
  {
    id: "inc-3",
    serviceId: "service-c-inventory",
    serviceName: "Inventory Service",
    severity: "warn",
    actionType: "Scale +1 replica",
    executor: "decision-engine",
    timestamp: "2026-08-15T04:10:00Z",
    details: "ADWIN drift detected, pre-warming an additional replica",
  },
  {
    id: "inc-4",
    serviceId: "service-e-payments",
    serviceName: "Payments Service",
    severity: "warn",
    actionType: "Pre-warm replica",
    executor: "decision-engine",
    timestamp: "2026-08-15T03:55:00Z",
    details: "Anomaly score crossed 0.5, pre-warming for anticipated load",
  },
];

export const driftAlertServices = services.filter((s) => s.driftDetected).map((s) => s.displayName);
