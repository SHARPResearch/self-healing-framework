import { Activity, Bot, TriangleAlert, Waves, Wrench } from "lucide-react";
import type { NotificationKind } from "../types";

export const KIND_LABEL: Record<NotificationKind, string> = {
  anomaly: "Anomaly",
  incident: "Incident",
  action: "Action",
  drift: "Drift",
  rca: "RCA",
};

export const KIND_ICON: Record<NotificationKind, typeof Activity> = {
  anomaly: Activity,
  incident: TriangleAlert,
  action: Wrench,
  drift: Waves,
  rca: Bot,
};

export function timeAgo(iso: string): string {
  const minutes = Math.max(1, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
