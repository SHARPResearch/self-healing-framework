// frontend\src\features\decisions\components\RunInspector.tsx
import { cn } from "@/lib/utils";
import { Bell, Clock, MailCheck, X } from "lucide-react";
import type { FlowStepDetail, RunNode, RunNodeState } from "../types";
import { formatClock, formatDuration } from "../lib/format";

const TONE_TEXT: Record<NonNullable<FlowStepDetail["tone"]>, string> = {
  default: "text-foreground",
  good: "text-status-healthy",
  warn: "text-status-degrade",
  bad: "text-status-critical",
  accent: "text-status-warn",
};

const STATE_TEXT: Record<RunNodeState, string> = {
  pending: "text-muted-foreground",
  active: "text-status-active",
  success: "text-status-healthy",
  shadow: "text-status-shadow",
  blocked: "text-status-critical",
  escalated: "text-status-escalated",
  failed: "text-destructive",
  skipped: "text-muted-foreground/70",
};

interface Props {
  node: RunNode | null;
  onClose: () => void;
}

/** Details for the step the operator clicked. Every row is a value we actually stored. */
export function RunInspector({ node, onClose }: Props) {
  if (!node) {
    return (
      <div className="rounded-xl border border-dashed border-border/60 p-4 text-xs text-muted-foreground">
        Click any step in the diagram to see the numbers behind it.
      </div>
    );
  }

  const Icon = node.icon;

  return (
    <div className="rounded-xl border border-border/60 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <Icon className={cn("mt-0.5 size-4 shrink-0", STATE_TEXT[node.state])} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <p className="truncate text-sm font-semibold">{node.title}</p>
              <span className="rounded-full bg-muted px-1.5 py-px font-mono text-[9px] text-muted-foreground">
                {node.stage}
              </span>
            </div>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {node.subtitle}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Clear selection"
          className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <X className="size-3.5" />
        </button>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2 border-y border-border/40 py-2 text-[10px] text-muted-foreground">
        <span className={cn("font-medium uppercase", STATE_TEXT[node.state])}>
          {node.state}
        </span>
        <span className="flex items-center gap-1">
          <Clock className="size-3" />
          {node.durationMs === null ? "not instrumented" : formatDuration(node.durationMs)}
          {node.durationMs !== null && !node.measured && " (span)"}
        </span>
        {node.notifications.length > 0 && (
          <span className="flex items-center gap-1">
            <Bell className="size-3" />
            {node.notifications.length}
          </span>
        )}
      </div>

      {node.note && (
        <p className="mt-2 rounded-md bg-muted/60 px-2 py-1.5 text-[11px] leading-snug">
          {node.note}
        </p>
      )}

      <dl className="mt-2.5 space-y-1">
        {node.details.map((detail, i) => (
          <div
            key={`${detail.label}-${i}`}
            className="flex items-baseline justify-between gap-3 text-[11px]"
          >
            <dt className="shrink-0 text-muted-foreground">{detail.label}</dt>
            <dd
              className={cn(
                "text-right break-words",
                TONE_TEXT[detail.tone ?? "default"],
                detail.mono && "font-mono",
              )}
            >
              {detail.value}
            </dd>
          </div>
        ))}
      </dl>

      {node.notifications.length > 0 && (
        <div className="mt-3 border-t border-border/40 pt-2">
          <p className="mb-1.5 flex items-center gap-1 text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
            <MailCheck className="size-3" />
            Notifications
          </p>
          <ul className="space-y-1.5">
            {node.notifications.map((n) => (
              <li key={n.id} className="text-[10px] leading-snug">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-medium" title={n.subject}>
                    {n.subject}
                  </span>
                  <span className="shrink-0 font-mono text-muted-foreground">
                    {formatClock(n.at)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-muted-foreground">
                  <span
                    className={cn(
                      "font-mono",
                      n.status === "SENT" && "text-status-healthy",
                      n.status === "FAILED" && "text-status-critical",
                      (n.status === "PENDING" || n.status === "SKIPPED") &&
                        "text-status-degrade",
                    )}
                  >
                    {n.status}
                  </span>
                  {n.recipient && <span className="truncate">→ {n.recipient}</span>}
                  {n.error && (
                    <span className="truncate text-status-critical" title={n.error}>
                      {n.error}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
