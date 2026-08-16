import { cn } from "@/lib/utils";
import type { Severity } from "@/features/dashboard/types";

const SEVERITY_LABEL: Record<Severity, string> = {
  watch: "Watch",
  warn: "Warn",
  degrade: "Degrade",
  critical: "Critical",
};

const SEVERITY_CLASS: Record<Severity, string> = {
  watch: "bg-status-watch/15 text-status-watch",
  warn: "bg-status-warn/15 text-status-warn",
  degrade: "bg-status-degrade/15 text-status-degrade",
  critical: "bg-status-critical/15 text-status-critical",
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        SEVERITY_CLASS[severity],
        className,
      )}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
