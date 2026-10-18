import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ScorePoint } from "../types";

interface LiveScoreChartProps {
  points: ScorePoint[];
  height?: number;
  stroke?: string;
}

/**
 * A service's normalized anomaly score. 0.5 is the serving model version's calibrated POT
 * threshold, so the dashed line means "alarm" for every service and every version.
 */
export function LiveScoreChart({ points, height = 120, stroke = "var(--foreground)" }: LiveScoreChartProps) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
        <XAxis dataKey="step" hide />
        <YAxis
          domain={[0, 1]}
          ticks={[0, 0.5, 1]}
          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value: number) => [value.toFixed(3), "score"]}
          labelFormatter={(step) => `step ${step}`}
          contentStyle={{
            background: "var(--popover)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            fontSize: 12,
          }}
        />
        <ReferenceLine y={0.5} stroke="var(--status-critical)" strokeDasharray="4 4" />
        <Line type="monotone" dataKey="score" stroke={stroke} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
