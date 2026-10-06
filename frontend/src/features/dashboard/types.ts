import type { Severity } from "@/shared/types";

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
  deltaLabel?: string;
  deltaDirection?: "up" | "down";
  deltaTone?: "positive" | "negative";
}
