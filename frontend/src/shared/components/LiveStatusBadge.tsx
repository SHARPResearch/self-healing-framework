import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useLiveStore } from "@/shared/store/liveStore";

const LABEL = {
  live: "Live",
  connecting: "Connecting",
  reconnecting: "Reconnecting",
  offline: "Offline: sample data",
} as const;

const DOT = {
  live: "bg-status-healthy",
  connecting: "bg-muted-foreground animate-pulse",
  reconnecting: "bg-status-warn animate-pulse",
  offline: "bg-muted-foreground",
} as const;

/** Header pill: is the UI on live ml-backend data or on the bundled mock data? */
export function LiveStatusBadge() {
  const status = useLiveStore((s) => s.status);
  const health = useLiveStore((s) => s.health);

  const detail =
    status === "offline"
      ? "services/ml-backend is not reachable on :8000, so pages show their bundled sample data. It reconnects automatically."
      : health
        ? `Store: ${health.store === "timescaledb" ? "TimescaleDB" : "in memory"} · Redis: ${health.redis ? "on" : "off"} · ${health.services} services at ${health.eventsPerSec} events/s${health.paused ? " (paused)" : ""}`
        : "Waiting for ml-backend.";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            "inline-flex cursor-default items-center gap-1.5 rounded-full border border-border/60 px-2.5 py-1 text-xs",
            status === "live" ? "text-foreground" : "text-muted-foreground",
          )}
        >
          <span className={cn("size-1.5 rounded-full", DOT[status])} />
          {LABEL[status]}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{detail}</TooltipContent>
    </Tooltip>
  );
}
