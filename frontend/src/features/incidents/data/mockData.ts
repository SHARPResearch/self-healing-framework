import type { DeltaStat, IncidentReportRange, IncidentTrendPoint } from "../types";

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

/**
 * Deterministic (not Math.random) synthetic trend so the chart stays
 * reproducible across renders/screenshots. Combines a slow sine wave with a
 * short repeating offset to look like a plausible daily incident count.
 */
function buildTrend(days: number): IncidentTrendPoint[] {
  const end = new Date("2026-08-16T00:00:00Z");
  return Array.from({ length: days }, (_, i) => {
    const date = new Date(end);
    date.setUTCDate(end.getUTCDate() - (days - 1 - i));
    const count = Math.round(16 + 9 * Math.sin(i / 4) + ((i * 3) % 7));
    return {
      label: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      count,
    };
  });
}

export const incidentTrendByRange: Record<IncidentReportRange, IncidentTrendPoint[]> = {
  "7d": trend7d,
  "30d": buildTrend(30),
  "90d": buildTrend(90),
};

export const incidentSummaryStats: DeltaStat[] = [
  {
    id: "critical-incidents",
    label: "Critical incidents",
    value: "321",
    deltaLabel: "12% vs last week",
    deltaDirection: "up",
    deltaTone: "negative",
  },
  {
    id: "total-incidents",
    label: "Total incidents",
    value: "1,120",
    deltaLabel: "4% vs last week",
    deltaDirection: "down",
    deltaTone: "positive",
  },
];
