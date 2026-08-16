import type { IncidentReportRange, IncidentTrendPoint } from "../types";

/**
 * Mock data only -- no backend exists yet. Trend counts represent incidents
 * opened per day (an anomaly score crossing the warn threshold), independent
 * from the dashboard's mean anomaly score trend.
 */

const trend7d: IncidentTrendPoint[] = [
  { label: "Aug 10", count: 14 },
  { label: "Aug 11", count: 9 },
  { label: "Aug 12", count: 22 },
  { label: "Aug 13", count: 11 },
  { label: "Aug 14", count: 17 },
  { label: "Aug 15", count: 26 },
  { label: "Aug 16", count: 8 },
];

export const incidentTrendByRange: Record<IncidentReportRange, IncidentTrendPoint[]> = {
  "7d": trend7d,
  "30d": [],
  "90d": [],
};
