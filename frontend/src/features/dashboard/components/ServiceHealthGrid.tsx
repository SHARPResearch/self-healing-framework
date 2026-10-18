import { AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Sparkline } from "@/shared/components/Sparkline";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { ServiceHealth } from "../types";
import type { LiveServiceHealth } from "@/features/lifecycle/types";

const STATUS_TEXT_CLASS: Record<ServiceHealth["status"], string> = {
  watch: "text-status-watch",
  warn: "text-status-warn",
  degrade: "text-status-degrade",
  critical: "text-status-critical",
};

function ServiceTile({ service }: { service: ServiceHealth | LiveServiceHealth }) {
  const isCritical = service.status === "critical";
  const lifecycle = "phase" in service ? service : null;

  return (
    <Card
      className={cn(
        "border-border/60 transition-shadow",
        isCritical && "border-status-critical/50 shadow-[0_0_0_1px_var(--status-critical)]",
      )}
    >
      <CardContent className="flex items-start justify-between gap-3 py-4">
        <div>
          <p className="text-sm font-medium">{service.displayName}</p>
          <p className="text-xs text-muted-foreground">{service.serviceId}</p>
          <SeverityBadge severity={service.status} className="mt-2" />
          {lifecycle && (
            <p className="mt-2 font-mono text-[11px] text-muted-foreground">
              model v{lifecycle.modelVersion} · {lifecycle.phase}
              {lifecycle.openQueries > 0 && <span className="text-status-warn"> · asking operator</span>}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          <p className={cn("text-lg font-semibold tabular-nums", STATUS_TEXT_CLASS[service.status])}>
            {service.anomalyScore.toFixed(2)}
          </p>
          <Sparkline
            values={service.scoreHistory}
            className={STATUS_TEXT_CLASS[service.status]}
          />
          {service.driftDetected && (
            <span className="flex items-center gap-1 text-[11px] text-status-warn">
              <AlertTriangle className="size-3" />
              drift
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function ServiceHealthGrid({ services }: { services: ServiceHealth[] }) {
  return (
    <div>
      <h3 className="mb-1 text-base font-semibold">Service health</h3>
      <p className="mb-4 text-sm text-muted-foreground">
        Live status per monitored service, {services.length} total.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {services.map((service) => (
          <ServiceTile key={service.serviceId} service={service} />
        ))}
      </div>
    </div>
  );
}
