import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { IncidentTrendPoint } from "../types";

interface IncidentTrendChartProps {
  data: IncidentTrendPoint[];
}

export function IncidentTrendChart({ data }: IncidentTrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <XAxis
          dataKey="label"
          tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: "var(--popover)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            fontSize: 12,
          }}
        />
        <Area type="monotone" dataKey="count" stroke="var(--primary)" fill="var(--primary)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
