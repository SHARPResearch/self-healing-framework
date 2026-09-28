import { CheckCircle2, Loader2, Sparkles, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { useRemediationStore } from "@/shared/store/remediationStore";

/**
 * Shared between Dashboard and Incidents (SimulateAnomalyTrigger lives on
 * both) so the "adaptive RL decision engine" demo flow only exists once.
 * Illustrates the intended behavior of Doc1's Component 4 -- adaptive-
 * pipeline/ has no trained model yet (scaffold only, see root CLAUDE.md), so
 * this is explicitly labeled simulated rather than a real policy inference.
 */
export function RlPolicyEvaluationBanner() {
  const evaluation = useRemediationStore((s) => s.evaluation);
  const executeAction = useRemediationStore((s) => s.executeAction);
  const dismiss = useRemediationStore((s) => s.dismiss);

  if (!evaluation) return null;

  return (
    <div
      className={cn(
        "rounded-lg border px-4 py-3",
        evaluation.status === "executed"
          ? "border-status-healthy/40 bg-status-healthy/10"
          : "border-border/60 bg-card",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          {evaluation.status === "executed" ? (
            <CheckCircle2 className="size-4 shrink-0 text-status-healthy" />
          ) : (
            <Sparkles className="size-4 shrink-0 text-muted-foreground" />
          )}
          <p className="text-sm font-medium">
            {evaluation.status === "evaluating" && `Evaluating RL policy for ${evaluation.serviceName}…`}
            {evaluation.status === "ready" && `Recommended actions for ${evaluation.serviceName}`}
            {evaluation.status === "executed" && `Executed for ${evaluation.serviceName}`}
          </p>
        </div>
        <button
          type="button"
          onClick={dismiss}
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label="Dismiss"
        >
          <X className="size-4" />
        </button>
      </div>

      {evaluation.status === "evaluating" && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          Scoring graduated remediation actions against the current anomaly score…
        </div>
      )}

      {evaluation.status === "ready" && (
        <div className="mt-3 space-y-2.5">
          {evaluation.actions.map((action, i) => (
            <div key={action.label} className="flex items-center gap-3">
              <span className={cn("w-40 shrink-0 text-xs", i === 0 && "font-medium")}>{action.label}</span>
              <Progress value={action.confidence * 100} className="h-1.5" />
              <span className="w-10 shrink-0 text-right font-mono text-xs text-muted-foreground">
                {Math.round(action.confidence * 100)}%
              </span>
            </div>
          ))}
          <div className="flex items-center justify-between gap-3 pt-1">
            <p className="text-[11px] text-muted-foreground/70">
              Simulated — adaptive-pipeline's RL model isn't trained yet, this follows the rule-based
              graduated policy instead.
            </p>
            <Button size="sm" onClick={executeAction} className="shrink-0">
              Execute recommended action
            </Button>
          </div>
        </div>
      )}

      {evaluation.status === "executed" && (
        <p className="mt-1.5 text-xs text-muted-foreground">
          {evaluation.actions[0]?.label} dispatched (mock, nothing was sent). Recovery stats and the
          incident feed have been updated.
        </p>
      )}
    </div>
  );
}
