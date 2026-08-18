import { useMemo, useRef } from "react";
import ForceGraph3D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-3d";
import { useResizeObserver } from "@/shared/hooks/useResizeObserver";
import { resolveCardColor, resolveSeverityColors } from "../lib/severityColors";
import type { GraphEdge, GraphNodeInput } from "../types";

type GNode = NodeObject<GraphNodeInput>;
type GLink = LinkObject<GraphNodeInput, Record<string, never>>;

/**
 * P-13's own literal edge colour (#475569). There is no theme token
 * equivalent that reads clearly here: --color-border is a low alpha white
 * meant for CSS borders over a solid surface, and resolving it to an opaque
 * rgb would just be a very faint grey line in a 3D scene with no cascade to
 * blend against, so this one stays a literal.
 */
const EDGE_NEUTRAL = "#475569";

function linkTargetStatus(link: GLink): GraphNodeInput["status"] | undefined {
  return typeof link.target === "object" ? link.target?.status : undefined;
}

interface DependencyGraph3DProps {
  nodes: GraphNodeInput[];
  edges: GraphEdge[];
  hoveredId: string | null;
  onHoverChange: (id: string | null) => void;
  onSelect: (node: GraphNodeInput) => void;
}

export function DependencyGraph3D({
  nodes,
  edges,
  hoveredId,
  onHoverChange,
  onSelect,
}: DependencyGraph3DProps) {
  const { ref, size } = useResizeObserver<HTMLDivElement>({ width: 640, height: 520 });
  const fgRef = useRef<ForceGraphMethods<GNode, GLink> | undefined>(undefined);
  const colors = useMemo(() => resolveSeverityColors(), []);
  const background = useMemo(() => resolveCardColor(), []);

  // Deep cloned per nodes/edges identity change so the library's own
  // mutation of these objects (it adds x/y/z/vx/vy/vz and swaps link
  // source/target strings for node object references) never touches the
  // shared mock constants other pages also read from.
  const graphData = useMemo(
    () => ({
      nodes: nodes.map((n) => ({ ...n, id: n.serviceId })) as GNode[],
      links: edges.map((e) => ({ ...e })) as GLink[],
    }),
    [nodes, edges],
  );

  return (
    <div
      ref={ref}
      className="h-[520px] w-full overflow-hidden rounded-xl border border-border/60"
    >
      <ForceGraph3D<GraphNodeInput, Record<string, never>>
        ref={fgRef}
        graphData={graphData}
        width={size.width}
        height={size.height}
        backgroundColor={background}
        showNavInfo={false}
        nodeRelSize={5}
        nodeVal={(n) => (n.status === "critical" ? 3 : 1.4)}
        nodeColor={(n) => (n.serviceId === hoveredId ? "#ffffff" : colors[n.status])}
        nodeLabel={(n) =>
          `<div style="font:12px system-ui;background:#111;color:#fff;padding:6px 8px;border-radius:6px;border:1px solid #333">` +
          `<b>${n.displayName}</b><br/>${n.status} &bull; score ${n.anomalyScore.toFixed(2)}<br/>` +
          `${n.lastAction ? `Last action: ${n.lastAction}` : "No actions taken"}</div>`
        }
        linkColor={(l) => (linkTargetStatus(l) === "critical" ? colors.degrade : EDGE_NEUTRAL)}
        linkWidth={(l) => (linkTargetStatus(l) === "critical" ? 2 : 1)}
        linkDirectionalArrowLength={5}
        linkDirectionalArrowRelPos={1}
        linkDirectionalParticles={(l) => (linkTargetStatus(l) === "critical" ? 3 : 0)}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleColor={() => colors.degrade}
        onNodeHover={(n) => onHoverChange(n ? n.serviceId : null)}
        onNodeClick={(n) => onSelect(n)}
        enableNodeDrag={false}
        cooldownTicks={100}
      />
    </div>
  );
}
