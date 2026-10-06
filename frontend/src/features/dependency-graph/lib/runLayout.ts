import {
  forceCenter,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationNodeDatum,
} from "d3-force";
import type {
  GraphEdge,
  GraphNodeInput,
  PositionedEdge,
  PositionedNode,
} from "../types";

interface SimNode extends SimulationNodeDatum, GraphNodeInput {}

interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
}

/**
 * Runs the force simulation headless and returns settled positions.
 *
 * Doc4 P-13 warns against driving React state from simulation ticks. Rather
 * than mutating the SVG DOM directly (which would create a second source of
 * truth for positions and complicate the tooltip and click handlers), the
 * simulation is stopped up front and ticked synchronously to convergence, so
 * there are no ticks at render time at all. At this graph size that runs in
 * well under a frame.
 *
 * Pure function, no React -- call it from useMemo. d3-force seeds initial
 * positions deterministically (phyllotaxis spiral) and uses its own internal
 * PRNG for jiggle, so the same input always yields the same layout.
 */
export function runLayout(
  nodes: GraphNodeInput[],
  edges: GraphEdge[],
  width: number,
  height: number,
): { nodes: PositionedNode[]; edges: PositionedEdge[] } {
  const simNodes: SimNode[] = nodes.map((n) => ({ ...n }));
  const simLinks: SimLink[] = edges.map((e) => ({
    source: e.source,
    target: e.target,
  }));

  const simulation = forceSimulation(simNodes)
    .force(
      "link",
      forceLink<SimNode, SimLink>(simLinks)
        .id((d) => d.serviceId)
        .distance(220) // ← was 150
        .strength(0.35),
    )
    .force("charge", forceManyBody().strength(-2200)) // ← was -900
    .force("center", forceCenter(width / 2, height / 2))
    .stop();

  for (let i = 0; i < 400; i += 1) simulation.tick();

  const padding = 48;
  const positioned: PositionedNode[] = simNodes.map((n) => ({
    serviceId: n.serviceId,
    displayName: n.displayName,
    status: n.status,
    anomalyScore: n.anomalyScore,
    lastAction: n.lastAction,
    layer: n.layer,
    team: n.team,
    runtime: n.runtime,
    version: n.version,
    criticality: n.criticality,
    // Clamp so nodes near the edge are never clipped by the viewport.
    x: Math.max(padding, Math.min(width - padding, n.x ?? width / 2)),
    y: Math.max(padding, Math.min(height - padding, n.y ?? height / 2)),
  }));

  const byId = new Map(positioned.map((n) => [n.serviceId, n]));

  const positionedEdges: PositionedEdge[] = edges.flatMap((e) => {
    const source = byId.get(e.source);
    const target = byId.get(e.target);
    if (!source || !target) return [];
    return [
      {
        source,
        target,
        downstreamCritical: target.status === "critical",
        latencyMs: e.latencyMs,
      },
    ];
  });

  return { nodes: positioned, edges: positionedEdges };
}
