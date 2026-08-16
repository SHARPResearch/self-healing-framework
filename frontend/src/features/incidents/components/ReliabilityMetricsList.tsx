import { ArrowDown, ArrowUp } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import type { DeltaStat } from "../types";

interface ReliabilityMetricsListProps {
  metrics: DeltaStat[];
}

export function ReliabilityMetricsList({ metrics }: ReliabilityMetricsListProps) {
  return (
    <div className="divide-y divide-border/60">
      {metrics.map((metric, index) => {
        const Icon = metric.icon;
        const DeltaIcon = metric.deltaDirection === "up" ? ArrowUp : ArrowDown;
        return (
          <motion.div
            key={metric.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
            className="flex items-center justify-between gap-2 py-3"
          >
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {Icon && <Icon className="size-4" />}
              <span>{metric.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-semibold">{metric.value}</span>
              <span
                className={cn(
                  "flex size-7 items-center justify-center rounded-full",
                  metric.deltaTone === "positive"
                    ? "bg-status-healthy/15 text-status-healthy"
                    : "bg-status-critical/15 text-status-critical",
                )}
              >
                <DeltaIcon className="size-3.5" />
              </span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
