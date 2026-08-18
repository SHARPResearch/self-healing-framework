import { cn } from "@/lib/utils";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { GraphNodeInput } from "../types";

interface ServiceListProps {
  nodes: GraphNodeInput[];
  hoveredId: string | null;
  onHoverChange: (id: string | null) => void;
  onSelect: (node: GraphNodeInput) => void;
}

/**
 * The 3D canvas is a single WebGL surface, so it cannot offer the per-node
 * role="button"/tabIndex the 2D SVG graph used to. This list restores
 * keyboard parity: every row is focusable and Enter/Space-activatable, and
 * doubles as a legend and a hover-sync surface with the canvas.
 */
export function ServiceList({ nodes, hoveredId, onHoverChange, onSelect }: ServiceListProps) {
  return (
    <ul className="space-y-1.5">
      {nodes.map((node) => (
        <li key={node.serviceId}>
          <div
            role="button"
            tabIndex={0}
            aria-label={`${node.displayName}, ${node.status}, anomaly score ${node.anomalyScore.toFixed(2)}. Open incidents.`}
            onMouseEnter={() => onHoverChange(node.serviceId)}
            onMouseLeave={() => onHoverChange(null)}
            onFocus={() => onHoverChange(node.serviceId)}
            onBlur={() => onHoverChange(null)}
            onClick={() => onSelect(node)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(node);
              }
            }}
            className={cn(
              "flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-border/60 p-3 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              hoveredId === node.serviceId ? "bg-accent" : "hover:bg-accent/50",
            )}
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{node.displayName}</p>
              <p className="truncate font-mono text-xs text-muted-foreground">{node.serviceId}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">
                {node.anomalyScore.toFixed(2)}
              </span>
              <SeverityBadge severity={node.status} />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
