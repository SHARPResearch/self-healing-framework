import { cn } from "@/lib/utils";
import type { Severity } from "@/features/dashboard/types";

const SEVERITY_BAR_CLASS: Record<Severity, string> = {
  watch: "bg-status-watch",
  warn: "bg-status-warn",
  degrade: "bg-status-degrade",
  critical: "bg-status-critical",
};

interface AnomalyScoreBarsProps {
  score: number;
  severity: Severity;
}

export function AnomalyScoreBars({ score, severity }: AnomalyScoreBarsProps) {
  const filledBars = Math.round(score * 10);

  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1">
        {Array.from({ length: 10 }).map((_, index) => (
          <div
            key={index}
            className={cn(
              "h-5 w-1.5 rounded-full transition-all duration-500",
              index < filledBars ? SEVERITY_BAR_CLASS[severity] : "bg-muted/40 border border-border/30",
            )}
          />
        ))}
      </div>
      <span className="min-w-[3rem] font-mono text-sm font-medium text-foreground">
        {score.toFixed(2)}
      </span>
    </div>
  );
}
