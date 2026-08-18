import type { LucideIcon } from "lucide-react";

export type IncidentReportRange = "7d" | "30d" | "90d";

export interface IncidentTrendPoint {
  label: string;
  count: number;
}

export interface DeltaStat {
  id: string;
  label: string;
  value: string;
  deltaLabel: string;
  deltaDirection: "up" | "down";
  deltaTone: "positive" | "negative";
  icon?: LucideIcon;
}
