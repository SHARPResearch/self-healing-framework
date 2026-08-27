import type { GraphEdge, GraphNodeInput } from "../types";

export interface RootCauseResult {
  /** The node identified as the actual root cause. */
  rootCauseId: string;
  /** True when the node the caller asked about *is* the root cause. */
  isRootCause: boolean;
  /** Ids from the queried node down to the root cause, inclusive of both ends. */
  chain: string[];
}

/**
 * Walks downstream from `nodeId` (edges where it is the *source*, i.e. calls
 * that node makes -- per the "A -> B means A calls B, B is A's upstream"
 * convention in types.ts) looking for the deepest still-unhealthy node.
 *
 * A service's own elevated anomaly score is often just a symptom of a
 * dependency it calls being unhealthy. This returns the deepest unhealthy
 * node in that call chain, not just the queried node's own status, so the
 * detail panel can distinguish "this is the root cause" from "this is a
 * cascading symptom of X". Cycles are guarded against defensively even
 * though the current mock topology has none.
 */
export function identifyRootCause(
  nodeId: string,
  nodes: GraphNodeInput[],
  edges: GraphEdge[],
): RootCauseResult {
  const byId = new Map(nodes.map((n) => [n.serviceId, n]));
  const visited = new Set<string>();
  const chain: string[] = [nodeId];

  let current = nodeId;
  for (;;) {
    visited.add(current);
    const downstream = edges.find(
      (e) => e.source === current && !visited.has(e.target) && byId.has(e.target),
    );
    if (!downstream) break;

    const next = byId.get(downstream.target)!;
    if (next.status === "watch") break; // healthy dependency ends the chain

    chain.push(next.serviceId);
    current = next.serviceId;
  }

  return {
    rootCauseId: current,
    isRootCause: current === nodeId,
    chain,
  };
}
