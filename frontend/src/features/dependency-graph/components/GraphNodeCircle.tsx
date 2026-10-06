import type { Severity } from "@/shared/types";
import { useRef } from "react";
import type { PointerEvent } from "react";
import type { PositionedNode, ServiceLayer } from "../types";

// ─── Node sizing ───────────────────────────────────────────────────
const BASE_RADIUS = 28;

// Bigger nodes for critical services (higher criticality = bigger)
function radiusFor(criticality: number | undefined): number {
  const c = criticality ?? 0.6;
  return BASE_RADIUS + Math.round(c * 10); // 28..38
}

// ─── Status colors (ring + text) ──────────────────────────────────
const STATUS_STROKE: Record<Severity, string> = {
  watch: "var(--color-status-watch)",
  warn: "var(--color-status-warn)",
  degrade: "var(--color-status-degrade)",
  critical: "var(--color-status-critical)",
};

// ─── Layer colors (fill) ──────────────────────────────────────────
const LAYER_FILL: Record<ServiceLayer, { accent: string; label: string }> = {
  edge: { accent: "#3b82f6", label: "edge" },
  bff: { accent: "#a855f7", label: "bff" },
  domain: { accent: "#22c55e", label: "domain" },
  data: { accent: "#f59e0b", label: "data" },
  unknown: { accent: "#64748b", label: "unknown" },
};

interface GraphNodeCircleProps {
  node: PositionedNode;
  dimmed: boolean;
  selected: boolean;
  onHover: (node: PositionedNode | null) => void;
  onSelect: (node: PositionedNode) => void;
  onNodePointerDown: (
    node: PositionedNode,
    event: PointerEvent<SVGGElement>,
  ) => void;
  onNodePointerMove: (
    node: PositionedNode,
    event: PointerEvent<SVGGElement>,
  ) => void;
  onNodePointerUp: (event: PointerEvent<SVGGElement>) => void;
}

export function GraphNodeCircle({
  node,
  dimmed,
  selected,
  onHover,
  onSelect,
  onNodePointerDown,
  onNodePointerMove,
  onNodePointerUp,
}: GraphNodeCircleProps) {
  const draggedRef = useRef(false);
  const pointerStartRef = useRef<{ x: number; y: number } | null>(null);
  const r = radiusFor(node.criticality);
  const layer = (node.layer ?? "unknown") as ServiceLayer;
  const layerStyle = LAYER_FILL[layer];

  const isCritical = node.status === "critical";
  const isUnhealthy = node.status !== "watch";
  const statusColor = STATUS_STROKE[node.status];

  // Short label: "service-a-auth" -> "auth"
  const short = node.serviceId.split("-").slice(-1)[0] || node.serviceId;
  const versionTag = node.version ? `v${node.version.split(".")[0]}` : "";

  return (
    <>
      {/* ── Pulsing glow for unhealthy nodes ─────────────────────── */}
      {isUnhealthy && (
        <circle
          cx={node.x}
          cy={node.y}
          r={isCritical ? r + 12 : r + 7}
          fill={statusColor}
          filter="url(#node-glow)"
          opacity={isCritical ? 0.9 : 0.35}
          className={isCritical ? "animate-pulse-glow" : undefined}
          pointerEvents="none"
        />
      )}

      {/* ── Selection halo ───────────────────────────────────────── */}
      {selected && (
        <circle
          cx={node.x}
          cy={node.y}
          r={r + 8}
          fill="none"
          stroke={statusColor}
          strokeWidth={2}
          strokeDasharray="4 4"
          opacity={0.8}
          pointerEvents="none"
        />
      )}

      <g
        role="button"
        tabIndex={0}
        aria-label={`${node.displayName}, ${node.status}, layer ${layer}, anomaly ${node.anomalyScore.toFixed(2)}`}
        className="cursor-grab transition-opacity duration-150 focus-visible:outline-none active:cursor-grabbing"
        opacity={dimmed ? 0.2 : 1}
        onMouseEnter={() => onHover(node)}
        onMouseLeave={() => onHover(null)}
        onFocus={() => onHover(node)}
        onBlur={() => onHover(null)}
        onPointerDown={(event) => {
          draggedRef.current = false;
          pointerStartRef.current = {
            x: event.clientX,
            y: event.clientY,
          };
          onNodePointerDown(node, event);
        }}
        onPointerMove={(event) => {
          const start = pointerStartRef.current;
          if (
            start &&
            Math.hypot(event.clientX - start.x, event.clientY - start.y) > 3
          ) {
            draggedRef.current = true;
          }
          onNodePointerMove(node, event);
        }}
        onPointerUp={onNodePointerUp}
        onPointerCancel={onNodePointerUp}
        onClick={() => {
          if (draggedRef.current) {
            draggedRef.current = false;
            pointerStartRef.current = null;
            return;
          }
          pointerStartRef.current = null;
          onSelect(node);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(node);
          }
        }}
      >
        {/* ── Shadow / depth ──────────────────────────────────── */}
        <circle
          cx={node.x + 1}
          cy={node.y + 2}
          r={r}
          fill="black"
          opacity={0.25}
          pointerEvents="none"
        />

        {/* ── Main body — filled by severity color ─────────────── */}
        <circle
          cx={node.x}
          cy={node.y}
          r={r}
          fill={statusColor}
          stroke={layerStyle.accent}
          strokeWidth={3}
        />

        {/* ── Status ring around the body ─────────────────────── */}
        <circle
          cx={node.x}
          cy={node.y}
          r={r - 3}
          fill="none"
          stroke={statusColor}
          strokeWidth={isUnhealthy ? 3 : 1.5}
          opacity={isUnhealthy ? 1 : 0.5}
        />

        {/* ── Short service name (center) ─────────────────────── */}
        <text
          x={node.x}
          y={node.y}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={11}
          fontWeight={700}
          fill="#111827"
          pointerEvents="none"
          style={{ textTransform: "uppercase", letterSpacing: "0.5px" }}
        >
          {short.slice(0, 8)}
        </text>

        {/* ── Status dot badge (top-right corner) ─────────────── */}
        <circle
          cx={node.x + r * 0.72}
          cy={node.y - r * 0.72}
          r={6}
          fill={statusColor}
          stroke="var(--color-background)"
          strokeWidth={2}
          pointerEvents="none"
        />

        {/* ── Version tag (bottom-right corner) ───────────────── */}
        {versionTag && (
          <>
            <rect
              x={node.x + r * 0.45}
              y={node.y + r * 0.65}
              width={28}
              height={14}
              rx={7}
              fill="var(--color-background)"
              stroke={layerStyle.accent}
              strokeWidth={1}
              pointerEvents="none"
            />
            <text
              x={node.x + r * 0.45 + 14}
              y={node.y + r * 0.65 + 7}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={9}
              fontFamily="monospace"
              fontWeight={600}
              fill={layerStyle.accent}
              pointerEvents="none"
            >
              {versionTag}
            </text>
          </>
        )}

        {/* ── Display name BELOW the circle ───────────────────── */}
        <text
          x={node.x}
          y={node.y + r + 16}
          textAnchor="middle"
          fontSize={12}
          fontWeight={600}
          fill="var(--color-foreground)"
          pointerEvents="none"
        >
          {node.displayName}
        </text>

        {/* ── Service ID (smaller, under name) ────────────────── */}
        <text
          x={node.x}
          y={node.y + r + 30}
          textAnchor="middle"
          fontSize={10}
          fontFamily="monospace"
          fill="var(--color-muted-foreground)"
          pointerEvents="none"
        >
          {node.serviceId}
        </text>

        {/* ── Layer tag (top-left) ────────────────────────────── */}
        <rect
          x={node.x - r * 0.95}
          y={node.y - r * 0.95}
          width={40}
          height={14}
          rx={7}
          fill={layerStyle.accent}
          pointerEvents="none"
        />
        <text
          x={node.x - r * 0.95 + 20}
          y={node.y - r * 0.95 + 7}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={9}
          fontFamily="monospace"
          fontWeight={700}
          fill="black"
          pointerEvents="none"
          style={{ textTransform: "uppercase" }}
        >
          {layerStyle.label}
        </text>
      </g>
    </>
  );
}
