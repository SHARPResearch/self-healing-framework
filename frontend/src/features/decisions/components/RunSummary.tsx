// frontend\src\features\decisions\components\RunSummary.tsx
import { cn } from "@/lib/utils";
import type { DecisionRun } from "../types";
import { formatDuration } from "../lib/format";

const OUTCOME_CLASS: Record<string, string> = {
  AUTO_EXECUTE: "bg-status-healthy/12 text-status-healthy border-status-healthy/40",
  SHADOW_MODE: "bg-status-shadow/12 text-status-shadow border-status-shadow/40",
  HUMAN_LOOP: "bg-status-escalated/12 text-status-escalated border-status-escalated/40",
  BLOCK: "bg-status-critical/12 text-status-critical border-status-critical/40",
  NO_RULE_MATCHED: "bg-muted text-muted-foreground border-border",
  UNVALIDATED: "bg-status-warn/12 text-status-warn border-status-warn/40",
};

function Metric({
  label,
  value,
  tone,
  title,
}: {
  label: string;
  value: string;
  tone?: string;
  title?: string;
}) {
  return (
    <div title={title}>
      <p className="text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
        {label}
      </p>
      <p className={cn("mt-0.5 font-mono text-xs font-medium", tone)}>{value}</p>
    </div>
  );
}

/**
 * The one-line verdict for a run: what the engine decided, how long it took,
 * and — when it stopped — which step stopped it.
 */
export function RunSummary({ run }: { run: DecisionRun }) {
  const s = run.summary;
  const outcomeClass = OUTCOME_CLASS[s.outcome] ?? OUTCOME_CLASS.UNVALIDATED;
  const stoppedAt = run.nodes.find((n) => n.id === s.currentStepId);
  const failedNode = run.nodes.find((n) => n.state === "failed" || n.state === "blocked");

  return (
    <div className="rounded-xl border border-border/60 p-3">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5">
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold tracking-wider uppercase",
            outcomeClass,
          )}
        >
          {s.outcomeLabel}
        </span>

        <Metric label="Action" value={s.action} />
        <Metric label="Severity" value={s.severityLabel} />
        <Metric label="Confidence" value={`${Math.round(s.finalConf * 100)}%`} />
        <Metric label="Risk" value={s.risk} />

        <Metric
          label="Detect → decide"
          value={formatDuration(s.totalMs)}
          title="anomaly.detected_at → decision_log.created_at"
        />
        <Metric
          label="Pipeline compute"
          value={formatDuration(s.computeMs)}
          title="Sum of the instrumented stages"
        />
        <Metric
          label="Queued"
          value={formatDuration(s.queueMs)}
          title="Time the anomaly waited for the next pipeline cycle"
        />
        <Metric
          label="Notifications"
          value={String(s.notifications.length)}
          tone={s.notifications.length > 0 ? "text-foreground" : undefined}
        />

        {stoppedAt && (
          <Metric
            label="Stopped at"
            value={stoppedAt.title}
            tone={
              stoppedAt.state === "active"
                ? "text-status-active"
                : stoppedAt.state === "blocked" || stoppedAt.state === "failed"
                  ? "text-status-critical"
                  : "text-status-escalated"
            }
          />
        )}
      </div>

      {failedNode && (
        <p className="mt-2 border-t border-border/40 pt-2 text-[11px] text-muted-foreground">
          <span className="font-medium text-status-critical">
            {failedNode.title}
          </span>{" "}
          {failedNode.state === "blocked" ? "vetoed this action" : "failed"} —{" "}
          {failedNode.note ?? failedNode.subtitle}
        </p>
      )}
    </div>
  );
}
