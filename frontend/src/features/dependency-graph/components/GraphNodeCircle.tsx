import type { Severity } from "@/shared/types";
import type { PositionedNode } from "../types";

const NODE_RADIUS = 24;

const STROKE: Record<Severity, string> = {
  watch: "var(--color-status-watch)",
  warn: "var(--color-status-warn)",
  degrade: "var(--color-status-degrade)",
  critical: "var(--color-status-critical)",
};

// Dark, translucent fill tinted by status -- reads as "dark surface with a
// colored outline" rather than a solid status-colored disc.
const FILL: Record<Severity, string> = {
  watch: "color-mix(in oklch, var(--color-status-watch) 15%, var(--color-background))",
  warn: "color-mix(in oklch, var(--color-status-warn) 15%, var(--color-background))",
  degrade: "color-mix(in oklch, var(--color-status-degrade) 18%, var(--color-background))",
  critical: "color-mix(in oklch, var(--color-status-critical) 20%, var(--color-background))",
};

interface GraphNodeCircleProps {
  node: PositionedNode;
  dimmed: boolean;
  selected: boolean;
  onHover: (node: PositionedNode | null) => void;
  onSelect: (node: PositionedNode) => void;
}

export function GraphNodeCircle({ node, dimmed, selected, onHover, onSelect }: GraphNodeCircleProps) {
  const isCritical = node.status === "critical";
  const isGlowing = node.status === "critical" || node.status === "degrade" || node.status === "warn";
  // "svc-a-auth" -> "auth"; keeps the label inside a 24px circle.
  const short = node.serviceId.split("-").slice(2).join("-") || node.serviceId;

  return (
    <>
      {/* Rendered outside the interactive group on purpose: the pulse scales,
          and inside the group it would make the button's own hit area pulse
          with it. */}
      {isGlowing && (
        <circle
          cx={node.x}
          cy={node.y}
          r={isCritical ? NODE_RADIUS + 8 : NODE_RADIUS + 5}
          fill={STROKE[node.status]}
          filter="url(#node-glow)"
          opacity={isCritical ? undefined : 0.35}
          className={isCritical ? "animate-pulse-glow" : undefined}
          pointerEvents="none"
        />
      )}

      <g
        role="button"
        tabIndex={0}
        aria-label={`${node.displayName}, ${node.status}, anomaly score ${node.anomalyScore.toFixed(2)}`}
        className="cursor-pointer transition-opacity duration-150 focus-visible:outline-none"
        opacity={dimmed ? 0.25 : 1}
        onMouseEnter={() => onHover(node)}
        onMouseLeave={() => onHover(null)}
        onFocus={() => onHover(node)}
        onBlur={() => onHover(null)}
        onClick={() => onSelect(node)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(node);
          }
        }}
      >
        {selected && (
          <circle
            cx={node.x}
            cy={node.y}
            r={NODE_RADIUS + 6}
            fill="none"
            stroke={STROKE[node.status]}
            strokeWidth={1}
            strokeDasharray="3 3"
            opacity={0.7}
          />
        )}

        <circle
          cx={node.x}
          cy={node.y}
          r={NODE_RADIUS}
          fill={FILL[node.status]}
          stroke={STROKE[node.status]}
          strokeWidth={selected ? 2.5 : 1.5}
        />

        <text
          x={node.x}
          y={node.y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={10}
          fill={STROKE[node.status]}
          fontWeight={600}
          pointerEvents="none"
        >
          {short}
        </text>

        {/* Status dot badge, corner of the node -- matches the reference design. */}
        <circle
          cx={node.x + NODE_RADIUS * 0.62}
          cy={node.y - NODE_RADIUS * 0.62}
          r={5}
          fill={STROKE[node.status]}
          stroke="var(--color-background)"
          strokeWidth={1.5}
          pointerEvents="none"
        />

        <text
          x={node.x}
          y={node.y + NODE_RADIUS + 14}
          textAnchor="middle"
          fontSize={11}
          fill="var(--color-muted-foreground)"
          pointerEvents="none"
        >
          {node.displayName}
        </text>
      </g>
    </>
  );
}
