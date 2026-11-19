// frontend\src\features\decisions\components\FlowNode.tsx
import { cn } from "@/lib/utils";
import { Bell } from "lucide-react";
import type { RunNode, RunNodeState } from "../types";
import { formatDuration } from "../lib/format";

/**
 * One card in the run graph. Colour is the whole point of this component:
 * the border, icon and badge all inherit the node's state token, so a glance
 * at the diagram answers "where did this run stop, and why".
 */
const STATE: Record<
  RunNodeState,
  {
    ring: string;
    bg: string;
    text: string;
    label: string;
    tint: string;
  }
> = {
  pending: {
    ring: "border-status-idle/40",
    bg: "bg-card/60",
    text: "text-muted-foreground",
    label: "pending",
    tint: "var(--status-idle)",
  },
  active: {
    ring: "border-status-active",
    bg: "bg-status-active/10",
    text: "text-status-active",
    label: "running",
    tint: "var(--status-active)",
  },
  success: {
    ring: "border-status-healthy/70",
    bg: "bg-status-healthy/10",
    text: "text-status-healthy",
    label: "done",
    tint: "var(--status-healthy)",
  },
  shadow: {
    ring: "border-status-shadow/70",
    bg: "bg-status-shadow/10",
    text: "text-status-shadow",
    label: "shadow",
    tint: "var(--status-shadow)",
  },
  blocked: {
    ring: "border-status-critical/80",
    bg: "bg-status-critical/10",
    text: "text-status-critical",
    label: "blocked",
    tint: "var(--status-critical)",
  },
  escalated: {
    ring: "border-status-escalated/80",
    bg: "bg-status-escalated/10",
    text: "text-status-escalated",
    label: "escalated",
    tint: "var(--status-escalated)",
  },
  failed: {
    ring: "border-destructive",
    bg: "bg-destructive/10",
    text: "text-destructive",
    label: "failed",
    tint: "var(--destructive)",
  },
  skipped: {
    ring: "border-border/50 border-dashed",
    bg: "bg-card/20",
    text: "text-muted-foreground/70",
    label: "skipped",
    tint: "var(--status-idle)",
  },
};

interface Props {
  node: RunNode;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function FlowNode({ node, selected, onSelect }: Props) {
  const style = STATE[node.state];
  const Icon = node.icon;
  const terminal = node.kind === "terminal";
  const notificationCount = node.notifications.length;

  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      aria-pressed={selected}
      title={`${node.title} — ${style.label}${node.note ? `\n${node.note}` : ""}`}
      className={cn(
        "absolute flex flex-col justify-between overflow-hidden rounded-lg border px-2.5 py-2 text-left transition-colors",
        "hover:brightness-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
        style.ring,
        style.bg,
        node.state === "active" && "flow-node-active",
        node.state === "skipped" && "opacity-60",
        selected && "ring-2 ring-foreground/50",
      )}
      style={{
        left: node.x,
        top: node.y,
        width: node.w,
        height: node.h,
        // Drives the pulse-ring keyframe without a Tailwind arbitrary class.
        ["--flow-pulse-color" as string]: style.tint,
      }}
    >
      <div className="flex w-full items-start gap-1.5">
        <Icon
          className={cn("mt-px size-3.5 shrink-0", style.text)}
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "truncate text-[11px] leading-tight font-semibold",
              terminal ? "text-[11px]" : "",
            )}
          >
            {node.title}
          </p>
          <p className="mt-0.5 truncate text-[10px] leading-tight text-muted-foreground">
            {node.subtitle}
          </p>
        </div>
        {notificationCount > 0 && (
          <span
            className="flex shrink-0 items-center gap-0.5 rounded-full bg-background/80 px-1 py-px font-mono text-[9px] text-muted-foreground"
            title={`${notificationCount} notification${notificationCount === 1 ? "" : "s"}`}
          >
            <Bell className="size-2.5" aria-hidden="true" />
            {notificationCount}
          </span>
        )}
      </div>

      <div className="flex w-full items-center justify-between gap-1">
        <span
          className={cn(
            "shrink-0 rounded-full px-1 py-px text-[9px] font-medium tracking-wide uppercase",
            style.text,
          )}
          style={{ backgroundColor: "color-mix(in oklch, currentColor 12%, transparent)" }}
        >
          {style.label}
        </span>
        {node.badges.length > 0 && (
          <span
            className={cn(
              "min-w-0 truncate rounded px-1 py-px text-[9px] font-medium",
              node.badges[0].tone === "good" && "bg-status-healthy/15 text-status-healthy",
              node.badges[0].tone === "warn" && "bg-status-degrade/15 text-status-degrade",
              node.badges[0].tone === "bad" && "bg-status-critical/15 text-status-critical",
              node.badges[0].tone === "accent" && "bg-status-warn/15 text-status-warn",
              node.badges[0].tone === "default" && "bg-muted text-muted-foreground",
            )}
            title={node.badges.map((b) => b.label).join(" · ")}
          >
            {node.badges[0].label}
          </span>
        )}
        <span
          className="shrink-0 font-mono text-[9px] text-muted-foreground"
          title={
            node.measured
              ? "Measured"
              : node.durationMs === null
                ? "Not instrumented for this decision"
                : "Span estimate"
          }
        >
          {node.durationMs === null ? "—" : formatDuration(node.durationMs)}
          {node.measured ? "" : node.durationMs === null ? "" : "~"}
        </span>
      </div>

      {node.isNext && (
        <span className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full border border-status-active/50 bg-background px-1.5 py-px text-[9px] font-medium text-status-active">
          next
        </span>
      )}
    </button>
  );
}
