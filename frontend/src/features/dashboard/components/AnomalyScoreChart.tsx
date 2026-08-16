import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge } from "@/components/ui/badge";
import type { AnomalyTrendPoint } from "../types";

interface AnomalyScoreChartProps {
  data: AnomalyTrendPoint[];
  changePct: number;
}

/**
 * Matches the spec for AnomalyScoreChart in
 * docs/prompts/Doc4_Claude_Code_Agent_Prompts.md P-12: reference lines at 0.5
 * (warn) and 0.85 (critical), y axis fixed to 0..1.
 */
export function AnomalyScoreChart({ data, changePct }: AnomalyScoreChartProps) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <h3 className="text-base font-semibold">Anomaly score trend</h3>
        <Badge variant="secondary" className="text-status-healthy">
          {changePct >= 0 ? "+" : ""}
          {changePct}%
        </Badge>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Mean anomaly score across all services, last 7 days.
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(value: number) => value.toFixed(2)}
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              fontSize: 12,
            }}
          />
          <ReferenceLine y={0.5} stroke="var(--status-warn)" strokeDasharray="4 4" />
          <ReferenceLine y={0.85} stroke="var(--status-critical)" strokeDasharray="4 4" />
          <Line
            type="monotone"
            dataKey="score"
            stroke="var(--foreground)"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
