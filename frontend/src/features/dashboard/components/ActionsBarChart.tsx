import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import type { DailyMetricPoint } from "../types";

interface ActionsBarChartProps {
  data: DailyMetricPoint[];
  changePct?: number;
  title?: string;
  description?: string;
}

export function ActionsBarChart({
  data,
  changePct,
  title = "Recovery actions",
  description = "Actions dispatched by the decision engine, last 7 days.",
}: ActionsBarChartProps) {
  return (
    <div>
      <div className="mb-1 flex items-center gap-2">
        <h3 className="text-base font-semibold">{title}</h3>
        {changePct !== undefined && (
          <Badge variant="secondary" className="text-status-healthy">
            {changePct >= 0 ? "+" : ""}
            {changePct}%
          </Badge>
        )}
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        {description}
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
          <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} name="Decisions" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
