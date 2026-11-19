// frontend\src\features\decisions\components\DecisionFlow.tsx
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { GitBranch, ListTree, Loader2 } from "lucide-react";
import type { ApiDecision } from "@/lib/api";
import { useDecisionRun } from "../data/useDecisionRun";
import { buildSteps } from "../lib/steps";
import type { RunNode } from "../types";
import { FlowDiagram } from "./FlowDiagram";
import { RunInspector } from "./RunInspector";
import { RunSummary } from "./RunSummary";
import { StepCard } from "./StepCard";

interface Props {
  decision: ApiDecision;
  /** `compact` drops the summary strip — the modal already shows the verdict. */
  compact?: boolean;
  pollMs?: number;
}

type View = "graph" | "steps";

/**
 * The decision's run, as a graph of the seven pipeline stages plus the four
 * routing outcomes. Side tables (execution, escalation, shadow, notifications)
 * are loaded lazily by `useDecisionRun`; the graph still renders if any of
 * them is unreachable.
 */
export function DecisionFlow({ decision, compact = false, pollMs = 0 }: Props) {
  const { run, loading, error } = useDecisionRun(decision, { pollMs });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("graph");

  // Drop the selection when the decision changes underneath us.
  useEffect(() => {
    setSelectedId(null);
  }, [decision.decision_id]);

  const selected: RunNode | null =
    run?.nodes.find((n) => n.id === selectedId) ?? null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="inline-flex rounded-lg border border-border/60 p-0.5">
          {(
            [
              { id: "graph" as const, label: "Flow", icon: GitBranch },
              { id: "steps" as const, label: "Steps", icon: ListTree },
            ] satisfies Array<{ id: View; label: string; icon: typeof GitBranch }>
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium",
                view === tab.id
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <tab.icon className="size-3" />
              {tab.label}
            </button>
          ))}
        </div>

        {loading && (
          <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            loading side effects…
          </span>
        )}
        {!loading && error && (
          <span className="text-[10px] text-status-critical">{error}</span>
        )}
      </div>

      {view === "graph" ? (
        loading && !run ? (
          <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-border/60 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Building the run…
          </div>
        ) : run ? (
          <div className="space-y-3">
            {!compact && <RunSummary run={run} />}
            <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_260px]">
              <FlowDiagram
                run={run}
                selectedId={selectedId}
                onSelect={(id) =>
                  setSelectedId((current) => (current === id ? null : id))
                }
              />
              <RunInspector node={selected} onClose={() => setSelectedId(null)} />
            </div>
          </div>
        ) : (
          <p className="rounded-xl border border-dashed border-border/60 p-6 text-center text-xs text-muted-foreground">
            No run to show — the decision id could not be resolved.
          </p>
        )
      ) : (
        <div className="space-y-0">
          {buildSteps(decision).map((step, i, all) => (
            <StepCard key={step.id} step={step} isLast={i === all.length - 1} />
          ))}
        </div>
      )}
    </div>
  );
}
