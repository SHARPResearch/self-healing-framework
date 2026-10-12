import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { ApiAppSnapshot, ApiInfraSnapshot } from "@/lib/api";

interface AnomalyChartProps {
  title: string;
  unit: string;
  data: Array<{ time: string; t: number; value: number }>;
  color?: string;
  /** ISO timestamp of the anomaly. Renders a vertical marker line. */
  markerTime?: string;
}

export function AnomalyChart({
  title,
  unit,
  data,
  color = "#3b82f6",
  markerTime,
}: AnomalyChartProps) {
  const markerValue = markerTime ? new Date(markerTime).getTime() : undefined;

  return (
    <div className="rounded-lg border border-border/60 bg-card/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium">{title}</span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {unit}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart
          data={data}
          margin={{ top: 6, right: 10, left: -10, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--color-border)"
            opacity={0.3}
          />
          <XAxis
            dataKey="t"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v) => {
              const d = new Date(v);
              return `${d.getHours().toString().padStart(2, "0")}:${d
                .getMinutes()
                .toString()
                .padStart(2, "0")}`;
            }}
            stroke="var(--color-muted-foreground)"
            fontSize={10}
            tickLine={false}
          />
          <YAxis
            stroke="var(--color-muted-foreground)"
            fontSize={10}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--color-popover)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(v) => new Date(v as number).toLocaleTimeString()}
            formatter={(value: any) => [
              `${Number(value).toFixed(2)} ${unit}`,
              title,
            ]}
          />
          {markerValue != null && (
            <ReferenceLine
              x={markerValue}
              stroke="var(--color-status-critical)"
              strokeDasharray="4 4"
              label={{
                value: "anomaly",
                position: "top",
                fill: "var(--color-status-critical)",
                fontSize: 10,
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Helpers to build chart series from evidence ──────────────────

export function buildLatencySeries(snapshots: ApiAppSnapshot[]) {
  return snapshots
    .filter((s) => s.latency_p99 != null)
    .map((s) => ({
      time: s.time,
      t: new Date(s.time).getTime(),
      value: s.latency_p99 ?? 0,
    }));
}

export function buildCpuSeries(snapshots: ApiInfraSnapshot[]) {
  return snapshots
    .filter((s) => s.cpu_usage_pct != null)
    .map((s) => ({
      time: s.time,
      t: new Date(s.time).getTime(),
      value: (s.cpu_usage_pct ?? 0) * 100,
    }));
}

export function buildErrorRateSeries(snapshots: ApiAppSnapshot[]) {
  return snapshots
    .filter((s) => s.error_rate != null)
    .map((s) => ({
      time: s.time,
      t: new Date(s.time).getTime(),
      value: (s.error_rate ?? 0) * 100,
    }));
}

export function buildRpsSeries(snapshots: ApiAppSnapshot[]) {
  return snapshots
    .filter((s) => s.rps != null)
    .map((s) => ({
      time: s.time,
      t: new Date(s.time).getTime(),
      value: s.rps ?? 0,
    }));
}

export function buildMemorySeries(snapshots: ApiInfraSnapshot[]) {
  return snapshots
    .filter((s) => s.mem_pct != null)
    .map((s) => ({
      time: s.time,
      t: new Date(s.time).getTime(),
      value: (s.mem_pct ?? 0) * 100,
    }));
}
