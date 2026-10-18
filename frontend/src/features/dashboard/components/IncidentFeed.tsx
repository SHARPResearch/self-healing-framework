import { CheckCircle2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { IncidentEntry } from "../types";

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(1, Math.round(diffMs / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function IncidentFeed({ incidents }: { incidents: IncidentEntry[] }) {
  return (
    <div>
      <h3 className="mb-1 text-base font-semibold">Incident feed</h3>
      <p className="mb-4 text-sm text-muted-foreground">
        Latest anomalies and remediation actions.
      </p>

      {incidents.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border py-10 text-muted-foreground">
          <CheckCircle2 className="size-6 text-status-healthy" />
          <p className="text-sm">No active incidents</p>
        </div>
      ) : (
        <ScrollArea className="h-[22rem] pr-3">
          <ul className="space-y-3">
            {incidents.map((incident) => (
              <li
                key={incident.id}
                className="rounded-lg border border-border/60 p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={incident.severity} />
                    <p className="text-sm font-medium">
                      {incident.serviceName}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {timeAgo(incident.timestamp)}
                  </span>
                </div>
                <p className="mt-1 text-sm">{incident.actionType}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {incident.details}
                </p>
              </li>
            ))}
          </ul>
        </ScrollArea>
      )}
    </div>
  );
}
