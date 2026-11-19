// frontend\src\features\decisions\components\FlowLegend.tsx
import type { RunNodeState } from "../types";

const ITEMS: Array<{ state: RunNodeState; label: string; hint: string }> = [
  { state: "active", label: "running", hint: "the engine is on this step now" },
  { state: "success", label: "done", hint: "step completed" },
  { state: "shadow", label: "shadow", hint: "evaluated, deliberately not executed" },
  { state: "escalated", label: "escalated", hint: "handed to a human" },
  { state: "blocked", label: "blocked", hint: "validation or guardrail veto" },
  { state: "failed", label: "failed", hint: "the action itself failed" },
  { state: "skipped", label: "not taken", hint: "branch not selected" },
];

const DOT: Record<RunNodeState, string> = {
  pending: "bg-status-idle/40",
  active: "bg-status-active",
  success: "bg-status-healthy",
  shadow: "bg-status-shadow",
  blocked: "bg-status-critical",
  escalated: "bg-status-escalated",
  failed: "bg-destructive",
  skipped: "bg-status-idle/40 border border-dashed border-status-idle/70",
};

/** Colour key for the run graph. Deliberately text-heavy: a demo audience reads the labels. */
export function FlowLegend() {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/40 pt-2.5">
      {ITEMS.map((item) => (
        <span
          key={item.state}
          className="flex items-center gap-1.5 text-[10px] text-muted-foreground"
          title={item.hint}
        >
          <span className={`size-2 rounded-full ${DOT[item.state]}`} />
          {item.label}
        </span>
      ))}
      <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <span className="h-px w-4 border-t border-dashed border-status-idle/70" />
        path not taken
      </span>
      <span
        className="text-[10px] text-muted-foreground"
        title="Durations come from decision_log.context.timings; “—” means the row predates the instrumentation"
      >
        <span className="font-mono">—</span> = not instrumented
      </span>
    </div>
  );
}
