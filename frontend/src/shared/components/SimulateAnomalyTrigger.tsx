import { Zap } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { services } from "@/features/dashboard/data/mockData";
import { useRemediationStore } from "@/shared/store/remediationStore";
import { SeverityBadge } from "./SeverityBadge";

// Limited to the mock services that already aren't healthy -- simulating a
// remediation on an already-healthy service wouldn't be a meaningful demo.
const ELIGIBLE_STATUSES = new Set(["warn", "degrade", "critical"]);

export function SimulateAnomalyTrigger() {
  const evaluation = useRemediationStore((s) => s.evaluation);
  const simulateAnomaly = useRemediationStore((s) => s.simulateAnomaly);
  const eligible = services.filter((s) => ELIGIBLE_STATUSES.has(s.status));

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={!!evaluation}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          <Zap className="mr-1.5 size-3.5" />
          Simulate anomaly
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Run the RL policy evaluator against
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {eligible.map((s) => (
          <DropdownMenuItem
            key={s.serviceId}
            onSelect={() => simulateAnomaly(s.serviceId)}
            className="flex items-center justify-between gap-2"
          >
            <span>{s.displayName}</span>
            <SeverityBadge severity={s.status} />
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
