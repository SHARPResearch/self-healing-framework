// frontend\src\features\decisions\components\FlowDiagram.tsx
import { useMemo } from "react";
import type { DecisionRun, RunEdge, RunEdgeState } from "../types";
import { FlowNode } from "./FlowNode";
import { FlowLegend } from "./FlowLegend";

const EDGE_COLOR: Record<RunEdgeState, string> = {
  done: "var(--status-healthy)",
  active: "var(--status-active)",
  skipped: "var(--status-idle)",
  failed: "var(--status-critical)",
};

function Edge({ edge, toX, toY }: { edge: RunEdge; toX?: number; toY?: number }) {
  const color = EDGE_COLOR[edge.state];
  const skipped = edge.state === "skipped";
  return (
    <g>
      <path
        d={edge.d}
        fill="none"
        stroke={color}
        strokeWidth={edge.state === "active" ? 2 : 1.5}
        strokeLinecap="round"
        strokeDasharray={skipped ? "3 5" : undefined}
        opacity={skipped ? 0.45 : edge.state === "done" ? 0.8 : 1}
        className={edge.state === "active" ? "flow-edge-active" : undefined}
      />
      {edge.arrow && toX !== undefined && toY !== undefined && (
        <polygon
          points={`${toX - 4},${toY - 8} ${toX + 4},${toY - 8} ${toX},${toY - 1}`}
          fill={color}
          opacity={skipped ? 0.45 : 1}
        />
      )}
      {edge.label && edge.labelX !== undefined && edge.labelY !== undefined && (
        <text
          x={edge.labelX}
          y={edge.labelY}
          className="fill-muted-foreground"
          fontSize={9}
          fontFamily="ui-monospace, SFMono-Regular, monospace"
        >
          {edge.label}
        </text>
      )}
    </g>
  );
}

interface Props {
  run: DecisionRun;
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Hide the legend when the caller already renders its own. */
  showLegend?: boolean;
}

export function FlowDiagram({
  run,
  selectedId,
  onSelect,
  showLegend = true,
}: Props) {
  const positions = useMemo(
    () => new Map(run.nodes.map((n) => [n.id, { x: n.x + n.w / 2, y: n.y }])),
    [run.nodes],
  );

  return (
    <div className="w-full">
      <div className="w-full overflow-x-auto pb-1">
        <div
          className="relative mx-auto"
          style={{ width: run.width, height: run.height }}
          role="group"
          aria-label="Decision run flow"
        >
          <svg
            width={run.width}
            height={run.height}
            className="absolute inset-0 overflow-visible"
            aria-hidden="true"
          >
            {run.edges.map((edge) => {
              const target = positions.get(edge.to);
              return (
                <Edge
                  key={edge.id}
                  edge={edge}
                  toX={target?.x}
                  toY={target?.y}
                />
              );
            })}
          </svg>

          {run.nodes.map((node) => (
            <FlowNode
              key={node.id}
              node={node}
              selected={selectedId === node.id}
              onSelect={onSelect}
            />
          ))}
        </div>
      </div>

      {showLegend && <FlowLegend />}
    </div>
  );
}
