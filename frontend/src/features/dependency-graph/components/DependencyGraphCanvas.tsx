import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { useResizeObserver } from "@/shared/hooks/useResizeObserver";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { graphEdges, graphNodes } from "../data/mockData";
import { runLayout } from "../lib/runLayout";
import { GraphEdgeLine } from "./GraphEdgeLine";
import { GraphNodeCircle } from "./GraphNodeCircle";
import type { PositionedNode } from "../types";

const MIN_SCALE = 0.5;
const MAX_SCALE = 2.5;

interface Transform {
  x: number;
  y: number;
  k: number;
}

const IDENTITY_TRANSFORM: Transform = { x: 0, y: 0, k: 1 };

export function DependencyGraphCanvas() {
  const navigate = useNavigate();
  const { ref, size } = useResizeObserver<HTMLDivElement>({ width: 900, height: 520 });
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<PositionedNode | null>(null);
  const [transform, setTransform] = useState<Transform>(IDENTITY_TRANSFORM);
  const panRef = useRef<{ pointerId: number; startX: number; startY: number; origX: number; origY: number } | null>(
    null,
  );

  const layout = useMemo(
    () => runLayout(graphNodes, graphEdges, size.width, size.height),
    [size.width, size.height],
  );

  // Which nodes/edges to highlight vs dim while a node is hovered or focused.
  const connected = useMemo(() => {
    if (!hovered) return null;
    const nodeIds = new Set([hovered.serviceId]);
    const edgeKeys = new Set<string>();
    for (const edge of layout.edges) {
      if (edge.source.serviceId === hovered.serviceId || edge.target.serviceId === hovered.serviceId) {
        nodeIds.add(edge.source.serviceId);
        nodeIds.add(edge.target.serviceId);
        edgeKeys.add(`${edge.source.serviceId}-${edge.target.serviceId}`);
      }
    }
    return { nodeIds, edgeKeys };
  }, [hovered, layout.edges]);

  // React's onWheel is passive by default, so preventDefault() inside it is a
  // no-op and the page scrolls along with the zoom. A native listener is the
  // only way to actually stop that.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;

      setTransform((prev) => {
        const factor = Math.exp(-e.deltaY * 0.001);
        const nextK = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.k * factor));
        // Keep the point under the cursor fixed while the scale changes.
        const nextX = cx - ((cx - prev.x) / prev.k) * nextK;
        const nextY = cy - ((cy - prev.y) / prev.k) * nextK;
        return { x: nextX, y: nextY, k: nextK };
      });
    };

    el.addEventListener("wheel", handleWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  const handleBackgroundPointerDown = (e: React.PointerEvent<SVGRectElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    panRef.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      origX: transform.x,
      origY: transform.y,
    };
  };

  const handleBackgroundPointerMove = (e: React.PointerEvent<SVGRectElement>) => {
    const pan = panRef.current;
    if (!pan || pan.pointerId !== e.pointerId) return;
    setTransform((prev) => ({
      ...prev,
      x: pan.origX + (e.clientX - pan.startX),
      y: pan.origY + (e.clientY - pan.startY),
    }));
  };

  const endPan = () => {
    panRef.current = null;
  };

  const zoomBy = (factor: number) => {
    setTransform((prev) => {
      const nextK = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.k * factor));
      const cx = size.width / 2;
      const cy = size.height / 2;
      const nextX = cx - ((cx - prev.x) / prev.k) * nextK;
      const nextY = cy - ((cy - prev.y) / prev.k) * nextK;
      return { x: nextX, y: nextY, k: nextK };
    });
  };

  const resetView = () => setTransform(IDENTITY_TRANSFORM);

  return (
    <div
      ref={ref}
      className="relative h-[520px] w-full overflow-hidden rounded-xl border border-border/60"
    >
      <svg
        ref={svgRef}
        width={size.width}
        height={size.height}
        role="img"
        aria-label="Service dependency graph, drag to pan and scroll to zoom"
        className="touch-none"
      >
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

        {/* Invisible full-size hit target for panning; a sibling of the nodes
            rather than an ancestor, so it never intercepts clicks on them. */}
        <rect
          x={0}
          y={0}
          width={size.width}
          height={size.height}
          fill="transparent"
          className="cursor-grab active:cursor-grabbing"
          onPointerDown={handleBackgroundPointerDown}
          onPointerMove={handleBackgroundPointerMove}
          onPointerUp={endPan}
          onPointerCancel={endPan}
        />

        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
          {layout.edges.map((edge) => {
            const key = `${edge.source.serviceId}-${edge.target.serviceId}`;
            return (
              <GraphEdgeLine
                key={key}
                edge={edge}
                dimmed={connected ? !connected.edgeKeys.has(key) : false}
              />
            );
          })}

          {layout.nodes.map((node) => (
            <GraphNodeCircle
              key={node.serviceId}
              node={node}
              dimmed={connected ? !connected.nodeIds.has(node.serviceId) : false}
              onHover={setHovered}
              onSelect={(n) => navigate(`/incidents?filter=${n.serviceId}`)}
            />
          ))}
        </g>
      </svg>

      <div className="absolute right-3 bottom-3 flex flex-col gap-1 rounded-lg border border-border/60 bg-popover/90 p-1 backdrop-blur-sm">
        <button
          type="button"
          onClick={() => zoomBy(1.3)}
          aria-label="Zoom in"
          className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <Plus className="size-4" />
        </button>
        <button
          type="button"
          onClick={() => zoomBy(1 / 1.3)}
          aria-label="Zoom out"
          className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <Minus className="size-4" />
        </button>
        <button
          type="button"
          onClick={resetView}
          aria-label="Reset view"
          className="flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <RotateCcw className="size-3.5" />
        </button>
      </div>

      {hovered && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 w-56 rounded-lg border border-border bg-popover p-3 shadow-lg"
          style={{
            left: Math.min(hovered.x * transform.k + transform.x + 32, size.width - 240),
            top: Math.max(hovered.y * transform.k + transform.y - 40, 8),
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
