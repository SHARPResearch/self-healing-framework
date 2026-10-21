import type { LucideIcon } from "lucide-react";

export type FlowStepStatus = "pending" | "running" | "done";

export interface FlowStep {
  id: string;
  title: string;
  icon: LucideIcon;
  status: FlowStepStatus;
  summary: string;
  details?: FlowStepDetail[];
}

export interface FlowStepDetail {
  label: string;
  value: string;
  tone?: "default" | "good" | "warn" | "bad" | "accent";
  mono?: boolean;
}
