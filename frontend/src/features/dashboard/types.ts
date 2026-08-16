/**
 * Severity taxonomy matches root CLAUDE.md's thresholds exactly, used
 * consistently across ml-backend and decision-engine: <0.5 watch, 0.5-0.7 warn,
 * 0.7-0.85 degrade, >0.85 critical.
 */
export type Severity = "watch" | "warn" | "degrade" | "critical";

export interface ServiceHealth {
  serviceId: string;
  displayName: string;
  status: Severity;
  anomalyScore: number;
  scoreHistory: number[];
  lastAction: string | null;
  lastActionAt: string | null;
  driftDetected: boolean;
}

export interface IncidentEntry {
  id: string;
  serviceId: string;
  serviceName: string;
  severity: Severity;
  actionType: string;
  executor: string;
  timestamp: string;
  details: string;
}

export interface DailyMetricPoint {
  label: string;
  value: number;
}

export interface AnomalyTrendPoint {
  label: string;
  score: number;
}

export interface StatCardData {
  label: string;
  value: string;
  deltaLabel: string;
  deltaDirection: "up" | "down";
  deltaTone: "positive" | "negative";
}
