import type { Severity } from "@/shared/types";
import type { PositionedNode } from "../types";

const NODE_RADIUS = 24;

const FILL: Record<Severity, string> = {
  watch: "var(--color-status-watch)",
  warn: "var(--color-status-warn)",
  degrade: "var(--color-status-degrade)",
  critical: "var(--color-status-critical)",
};

interface GraphNodeCircleProps {
  node: PositionedNode;
  onHover: (node: PositionedNode | null) => void;
  onSelect: (node: PositionedNode) => void;
}

export function GraphNodeCircle({ node, onHover, onSelect }: GraphNodeCircleProps) {
  const isCritical = node.status === "critical";
  // "svc-a-auth" -> "auth"; keeps the label inside a 24px circle.
  const short = node.serviceId.split("-").slice(2).join("-") || node.serviceId;

  return (
    <>
      {/* Rendered outside the interactive group on purpose: the pulse scales,
          and inside the group it would make the button's own hit area pulse
          with it. */}
      {isCritical && (
        <circle
          cx={node.x}
          cy={node.y}
          r={NODE_RADIUS + 8}
          fill={FILL.critical}
          filter="url(#node-glow)"
          className="animate-pulse-glow"
          pointerEvents="none"
        />
      )}

      <g
        role="button"
        tabIndex={0}
        aria-label={`${node.displayName}, ${node.status}, anomaly score ${node.anomalyScore.toFixed(2)}`}
        className="cursor-pointer focus-visible:outline-none"
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
        <circle
          cx={node.x}
          cy={node.y}
          r={NODE_RADIUS}
          fill={FILL[node.status]}
          stroke="var(--color-background)"
          strokeWidth={2}
        />

        <text
          x={node.x}
          y={node.y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={10}
          fill="#fff"
          fontWeight={600}
          pointerEvents="none"
        >
          {short}
        </text>

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
