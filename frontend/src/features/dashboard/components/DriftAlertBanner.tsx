import { useState } from "react";
import { TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DriftAlertBannerProps {
  affectedServices: string[];
}

/**
 * Per docs/prompts/Doc4_Claude_Code_Agent_Prompts.md P-12: shown when any
 * service has driftDetected true, dismissible, auto dismiss after 30s.
 */
export function DriftAlertBanner({ affectedServices }: DriftAlertBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || affectedServices.length === 0) return null;

  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border border-status-warn/40",
        "bg-status-warn/10 px-4 py-2.5 text-sm text-status-warn",
      )}
    >
      <div className="flex items-center gap-2">
        <TriangleAlert className="size-4 shrink-0" />
        <span>
          Model drift detected in: <span className="font-medium">{affectedServices.join(", ")}</span>
        </span>
      </div>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="rounded p-1 hover:bg-status-warn/15"
        aria-label="Dismiss drift alert"
      >
        <X className="size-4" />
      </button>
    </div>
  );
}
