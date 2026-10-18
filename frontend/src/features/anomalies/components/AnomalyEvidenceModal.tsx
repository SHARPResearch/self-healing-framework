import { useEffect } from "react";
import { X, Activity, AlertTriangle, Clock, Database } from "lucide-react";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { useAnomalyEvidence } from "../data/useAnomalyEvidence";
import {
  AnomalyChart,
  buildCpuSeries,
  buildErrorRateSeries,
  buildLatencySeries,
  buildMemorySeries,
  buildRpsSeries,
} from "./AnomalyChart";
import type { Severity } from "@/shared/types";

interface Props {
  anomalyId: string | null;
  onClose: () => void;
}

function toSeverity(sev?: string): Severity {
  if (sev === "high") return "critical";
  if (sev === "medium") return "warn";
  return "degrade";
}

export function AnomalyEvidenceModal({ anomalyId, onClose }: Props) {
  const { data, loading, error } = useAnomalyEvidence(anomalyId, 5000);

  // ESC closes
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!anomalyId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="relative max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-start justify-between gap-3 border-b border-border bg-background/95 p-4 backdrop-blur">
          <div className="flex-1">
            {loading && !data && (
              <p className="text-sm text-muted-foreground">Loading evidence…</p>
            )}
            {error && (
              <p className="text-sm text-destructive">Error: {error}</p>
            )}
            {data && (
              <>
                <div className="flex items-center gap-2">
                  <SeverityBadge severity={toSeverity(data.anomaly.severity)} />
                  <span className="text-lg font-semibold">
                    {data.anomaly.service_name ?? data.anomaly.service_id}
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  {data.anomaly.id}
                </p>
              </>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        {data && (
          <div className="space-y-4 p-4">
            {/* Summary row */}
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <SummaryCard
                icon={<AlertTriangle className="size-3.5" />}
                label="Score"
                value={`${(data.anomaly.anomaly_score * 100).toFixed(0)}%`}
                accent={
                  data.anomaly.anomaly_score >= 0.85
                    ? "text-red-600"
                    : "text-orange-500"
                }
              />
              <SummaryCard
                icon={<Activity className="size-3.5" />}
                label="Metric"
                value={data.anomaly.metric ?? "—"}
              />
              <SummaryCard
                icon={<Clock className="size-3.5" />}
                label="Detected"
                value={new Date(data.anomaly.detected_at).toLocaleTimeString()}
              />
              <SummaryCard
                icon={<Database className="size-3.5" />}
                label="Snapshots"
                value={`${data.counts.infra} infra · ${data.counts.app} app`}
              />
            </div>

            {/* Actual vs Expected */}
            {data.anomaly.actual_value != null &&
              data.anomaly.expected_value != null && (
                <div className="rounded-lg border border-border/60 bg-card/40 p-3">
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                    Anomaly Detail
                  </p>
                  <div className="flex items-baseline gap-3">
                    <span className="text-xl font-bold text-red-600">
                      {data.anomaly.actual_value.toFixed(2)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      vs expected{" "}
                      <span className="font-mono">
                        {data.anomaly.expected_value.toFixed(2)}
                      </span>
                    </span>
                    {data.anomaly.deviation_sigma != null && (
                      <span className="ml-auto font-mono text-xs">
                        σ = {data.anomaly.deviation_sigma.toFixed(1)}
                      </span>
                    )}
                  </div>
                </div>
              )}

            {/* Charts */}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <AnomalyChart
                title="P99 Latency"
                unit="ms"
                data={buildLatencySeries(data.app_snapshots)}
                color="#3b82f6"
                markerTime={data.anomaly.detected_at}
              />
              <AnomalyChart
                title="CPU Usage"
                unit="%"
                data={buildCpuSeries(data.infra_snapshots)}
                color="#f59e0b"
                markerTime={data.anomaly.detected_at}
              />
              <AnomalyChart
                title="Error Rate"
                unit="%"
                data={buildErrorRateSeries(data.app_snapshots)}
                color="#ef4444"
                markerTime={data.anomaly.detected_at}
              />
              <AnomalyChart
                title="Requests / sec"
                unit="rps"
                data={buildRpsSeries(data.app_snapshots)}
                color="#22c55e"
                markerTime={data.anomaly.detected_at}
              />
              <AnomalyChart
                title="Memory"
                unit="%"
                data={buildMemorySeries(data.infra_snapshots)}
                color="#a855f7"
                markerTime={data.anomaly.detected_at}
              />
            </div>

            {/* Window info */}
            {data.anomaly.snapshot_from && data.anomaly.snapshot_to && (
              <div className="rounded-lg border border-border/60 bg-muted/30 p-3 text-xs text-muted-foreground">
                <p className="font-mono">
                  Window:{" "}
                  {new Date(data.anomaly.snapshot_from).toLocaleString()} →{" "}
                  {new Date(data.anomaly.snapshot_to).toLocaleString()}
                </p>
                {data.anomaly.captured_at && (
                  <p className="mt-1 font-mono">
                    Captured at:{" "}
                    {new Date(data.anomaly.captured_at).toLocaleString()}
                  </p>
                )}
              </div>
            )}

            {data.app_snapshots.length === 0 &&
              data.infra_snapshots.length === 0 && (
                <div className="rounded-lg border border-dashed border-border p-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    No telemetry snapshots captured yet.
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Status: {data.anomaly.snapshot_status}
                  </p>
                </div>
              )}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/40 p-2.5">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <span className="font-mono text-[10px] uppercase tracking-wide">
          {label}
        </span>
      </div>
      <p className={`mt-1 text-sm font-semibold ${accent ?? ""}`}>{value}</p>
    </div>
  );
}
