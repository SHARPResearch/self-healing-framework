import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import type { DailyMetricPoint } from "../types";

interface ActionsBarChartProps {
  data: DailyMetricPoint[];
  changePct: number;
}

export function ActionsBarChart({ data, changePct }: ActionsBarChartProps) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <h3 className="text-base font-semibold">Recovery actions</h3>
        <Badge variant="secondary" className="text-status-healthy">
          {changePct >= 0 ? "+" : ""}
          {changePct}%
        </Badge>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Actions dispatched by the decision engine, last 7 days.
      </p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
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
            cursor={{ fill: "var(--accent)" }}
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              fontSize: 12,
            }}
          />
          <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} name="Actions" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
