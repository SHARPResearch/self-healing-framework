import { cn } from "@/lib/utils";
import type { ModelStage } from "../types";

const STAGE_CLASS: Record<ModelStage, string> = {
  WARM_UP: "bg-status-warn/15 text-status-warn",
  STREAMING: "bg-status-healthy/15 text-status-healthy",
  ARCHIVED: "bg-muted text-muted-foreground",
};

const STAGE_LABEL: Record<ModelStage, string> = {
  WARM_UP: "Warm up",
  STREAMING: "Streaming",
  ARCHIVED: "Archived",
};

export function StageBadge({ stage }: { stage: ModelStage }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        STAGE_CLASS[stage],
      )}
    >
      {STAGE_LABEL[stage]}
    </span>
  );
}
