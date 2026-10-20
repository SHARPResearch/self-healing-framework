import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Circle,
  Loader2,
} from "lucide-react";
import type { FlowStep, FlowStepDetail } from "../types";

interface Props {
  step: FlowStep;
  isLast: boolean;
}

const TONE_CLASSES: Record<string, string> = {
  default: "text-foreground",
  good: "text-green-600",
  warn: "text-amber-600",
  bad: "text-red-600",
  accent: "text-blue-600",
};

export function StepCard({ step, isLast }: Props) {
  const [expanded, setExpanded] = useState(true);
  const StepIcon = step.icon;

  return (
    <div className="relative flex gap-3">
      {/* vertical connector */}
      {!isLast && (
        <div className="absolute left-5 top-10 h-full w-px bg-border" />
      )}

      {/* status circle */}
      <div className="relative z-10 flex size-10 shrink-0 items-center justify-center rounded-full border-2 border-border bg-background">
        {step.status === "done" && (
          <CheckCircle2 className="size-5 text-green-600" />
        )}
        {step.status === "running" && (
          <Loader2 className="size-5 animate-spin text-blue-600" />
        )}
        {step.status === "pending" && (
          <Circle className="size-5 text-muted-foreground" />
        )}
      </div>

      {/* content */}
      <div className="flex-1 pb-6">
        <div className="rounded-lg border border-border/60 bg-card/40 p-3">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex w-full items-start justify-between gap-2 text-left"
          >
            <div className="flex items-start gap-2">
              <StepIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              <div>
                <p className="text-sm font-semibold">{step.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {step.summary}
                </p>
              </div>
            </div>
            {step.details && step.details.length > 0 && (
              <span className="mt-0.5 text-muted-foreground">
                {expanded ? (
                  <ChevronDown className="size-4" />
                ) : (
                  <ChevronRight className="size-4" />
                )}
              </span>
            )}
          </button>

          {expanded && step.details && step.details.length > 0 && (
            <div className="mt-3 space-y-1 border-t border-border/40 pt-3">
              {step.details.map((d, i) => (
                <DetailRow key={i} detail={d} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailRow({ detail }: { detail: FlowStepDetail }) {
  const tone = TONE_CLASSES[detail.tone ?? "default"];
  return (
    <div className="flex items-baseline justify-between gap-3 text-xs">
      <span className="text-muted-foreground">{detail.label}</span>
      <span className={`text-right ${tone} ${detail.mono ? "font-mono" : ""}`}>
        {detail.value}
      </span>
    </div>
  );
}
