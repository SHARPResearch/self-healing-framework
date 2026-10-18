import { useMemo } from "react";
import { useLiveStore } from "@/shared/store/liveStore";
import type { AnomalyTrendPoint, ServiceHealth, StatCardData } from "../types";

const TREND_POINTS = 60;

/**
 * Dashboard view of the live ml-backend fleet, or null while the backend has never been reached
 * (the page then renders its mock data). Every service steps on the same replay tick, so the
 * fleet trend is the per position mean of each service's latest score buffer.
 */
export function useLiveDashboard(): {
  services: ServiceHealth[];
  statCards: StatCardData[];
  trend: AnomalyTrendPoint[];
  driftServices: string[];
} | null {
  const ready = useLiveStore((s) => s.ready);
  const order = useLiveStore((s) => s.serviceOrder);
  const byId = useLiveStore((s) => s.services);
  const scores = useLiveStore((s) => s.scores);
  const summary = useLiveStore((s) => s.summary);

  return useMemo(() => {
    if (!ready) return null;
    const services = order.map((id) => byId[id]).filter(Boolean);
    const mean = services.length ? services.reduce((a, s) => a + s.anomalyScore, 0) / services.length : 0;
    const alarms = services.filter((s) => s.alarm).length;
    const quarantined = services.filter((s) => s.phase !== "stable").length;
    const openQueries = services.reduce((a, s) => a + s.openQueries, 0);

    const buffers = services.map((s) => (scores[s.serviceId] ?? []).slice(-TREND_POINTS));
    const len = Math.min(...buffers.map((b) => b.length), TREND_POINTS);
    const trend: AnomalyTrendPoint[] = [];
    for (let i = 0; len > 0 && i < len; i++) {
      const points = buffers.map((b) => b[b.length - len + i]);
      trend.push({
        label: String(points[0].step),
        score: Number((points.reduce((a, p) => a + p.score, 0) / points.length).toFixed(3)),
      });
    }

    const statCards: StatCardData[] = [
      {
        label: "Monitored services",
        value: String(services.length),
        deltaLabel: "replaying real SMD telemetry",
        deltaDirection: "up",
        deltaTone: "positive",
      },
      {
        label: "Services alarming",
        value: String(alarms),
        deltaLabel: alarms ? "above their calibrated threshold" : "all below threshold",
        deltaDirection: alarms ? "up" : "down",
        deltaTone: alarms ? "negative" : "positive",
      },
      {
        label: "Mean anomaly score",
        value: mean.toFixed(2),
        deltaLabel: "0.50 is each model's POT threshold",
        deltaDirection: mean >= 0.5 ? "up" : "down",
        deltaTone: mean >= 0.5 ? "negative" : "positive",
      },
      {
        label: "Model updates",
        value: String(summary?.modelUpdates ?? 0),
        deltaLabel: `${quarantined} in quarantine, ${openQueries} awaiting operator`,
        deltaDirection: quarantined + openQueries ? "up" : "down",
        deltaTone: quarantined + openQueries ? "negative" : "positive",
      },
    ];

    return {
      services,
      statCards,
      trend,
      driftServices: services.filter((s) => s.driftDetected).map((s) => s.displayName),
    };
  }, [ready, order, byId, scores, summary]);
}
