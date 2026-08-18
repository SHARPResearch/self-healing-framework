import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DeltaStat } from "../types";

interface IncidentSummaryStatsProps {
  stats: DeltaStat[];
}

export function IncidentSummaryStats({ stats }: IncidentSummaryStatsProps) {
  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
      {stats.map((stat) => {
        const Icon = stat.deltaDirection === "up" ? ArrowUp : ArrowDown;
        return (
          <div key={stat.id} className="flex flex-col gap-2">
            <span className="text-sm text-muted-foreground">{stat.label}</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-4xl font-semibold tracking-tight">{stat.value}</span>
              <span
                className={cn(
                  "flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium",
                  stat.deltaTone === "positive"
                    ? "bg-status-healthy/15 text-status-healthy"
                    : "bg-status-critical/15 text-status-critical",
                )}
              >
                <Icon className="size-3.5" />
                {stat.deltaLabel}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
