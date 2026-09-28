import type { Severity } from "@/shared/types";

/**
 * Kinds mirror the five things the real WebSocket multiplexes
 * (Doc1 §3.3): anomaly score updates, active incidents, action receipts,
 * drift alerts, and LLM RCA summaries.
 */
export type NotificationKind =
  | "anomaly"
  | "incident"
  | "action"
  | "drift"
  | "rca";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  severity: Severity;
  title: string;
  body: string;
  serviceId: string;
  timestamp: string;
  read: boolean;
}
