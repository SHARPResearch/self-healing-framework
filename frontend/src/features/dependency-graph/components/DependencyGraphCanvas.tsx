import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useResizeObserver } from "@/shared/hooks/useResizeObserver";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { graphEdges, graphNodes } from "../data/mockData";
import { runLayout } from "../lib/runLayout";
import { GraphEdgeLine } from "./GraphEdgeLine";
import { GraphNodeCircle } from "./GraphNodeCircle";
import type { PositionedNode } from "../types";

export function DependencyGraphCanvas() {
  const navigate = useNavigate();
  const { ref, size } = useResizeObserver<HTMLDivElement>({ width: 900, height: 520 });
  const [hovered, setHovered] = useState<PositionedNode | null>(null);

  const layout = useMemo(
    () => runLayout(graphNodes, graphEdges, size.width, size.height),
    [size.width, size.height],
  );

  return (
    <div ref={ref} className="relative h-[520px] w-full overflow-hidden rounded-xl border border-border/60">
      <svg width={size.width} height={size.height} role="img" aria-label="Service dependency graph">
        <defs>
          <filter id="node-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="6" />
          </filter>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-border)" />
          </marker>
          <marker id="arrow-critical" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-status-degrade)" />
          </marker>
        </defs>

        {layout.edges.map((edge) => (
          <GraphEdgeLine key={`${edge.source.serviceId}-${edge.target.serviceId}`} edge={edge} />
        ))}

        {layout.nodes.map((node) => (
          <GraphNodeCircle
            key={node.serviceId}
            node={node}
            onHover={setHovered}
            onSelect={(n) => navigate(`/incidents?filter=${n.serviceId}`)}
          />
        ))}
      </svg>

      {hovered && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 w-56 rounded-lg border border-border bg-popover p-3 shadow-lg"
          style={{
            left: Math.min(hovered.x + 32, size.width - 240),
            top: Math.max(hovered.y - 40, 8),
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-medium">{hovered.displayName}</p>
            <SeverityBadge severity={hovered.status} />
          </div>
          <p className="mt-1 font-mono text-xs text-muted-foreground">{hovered.serviceId}</p>
          <p className="mt-2 text-xs">
            Anomaly score <span className="font-mono font-medium">{hovered.anomalyScore.toFixed(2)}</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {hovered.lastAction ? `Last action: ${hovered.lastAction}` : "No actions taken"}
          </p>
        </div>
      )}
    </div>
  );
}
