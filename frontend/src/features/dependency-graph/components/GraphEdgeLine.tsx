import type { PositionedEdge } from "../types";

const NODE_RADIUS = 24;

/**
 * Draws an A -> B edge, stopped short of the target circle so the arrowhead
 * sits on the rim rather than under the node.
 */
export function GraphEdgeLine({ edge }: { edge: PositionedEdge }) {
  const { source, target, downstreamCritical } = edge;

  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const length = Math.hypot(dx, dy) || 1;
  const ux = dx / length;
  const uy = dy / length;

  const x1 = source.x + ux * NODE_RADIUS;
  const y1 = source.y + uy * NODE_RADIUS;
  const x2 = target.x - ux * (NODE_RADIUS + 8);
  const y2 = target.y - uy * (NODE_RADIUS + 8);

  // Colours come from theme tokens rather than P-13's hardcoded hex, matching
  // the substitution the dashboard already made against P-12's palette.
  const stroke = downstreamCritical ? "var(--color-status-degrade)" : "var(--color-border)";

  return (
    <line
      x1={x1}
      y1={y1}
      x2={x2}
      y2={y2}
      stroke={stroke}
      strokeWidth={downstreamCritical ? 2 : 1.5}
      strokeDasharray={downstreamCritical ? "6 4" : undefined}
      markerEnd={downstreamCritical ? "url(#arrow-critical)" : "url(#arrow)"}
    >
      {downstreamCritical && (
        <animate attributeName="stroke-dashoffset" from="20" to="0" dur="1s" repeatCount="indefinite" />
      )}
    </line>
  );
}
