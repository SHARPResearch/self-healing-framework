import type { Severity } from "@/shared/types";

/**
 * A node is one Kubernetes Deployment in the selfheal-apps namespace.
 * An edge A -> B means "A calls B", so B is A's upstream -- built from the
 * selfheal.io/upstreams annotation in the real system (Doc1 §5).
 */
export interface GraphEdge {
  source: string;
  target: string;
  /** Hand-authored, plausible latency for the detail panel -- see data/mockData.ts. */
  latencyMs: number;
}

export type ServiceLayer = "edge" | "bff" | "domain" | "data" | "unknown";

export interface GraphNodeInput {
  serviceId: string;
  displayName: string;
  status: Severity;
  anomalyScore: number;
  lastAction: string | null;

  // NEW — optional so existing mock data doesn't break
  layer?: ServiceLayer;
  team?: string;
  runtime?: string;
  version?: string;
  criticality?: number; // 0..1 — controls node size
}

/** A node after the force layout has assigned it a position. */
export interface PositionedNode extends GraphNodeInput {
  x: number;
  y: number;
}

export interface PositionedEdge {
  source: PositionedNode;
  target: PositionedNode;
  /** True when the callee is critical, which is what turns the edge amber. */
  downstreamCritical: boolean;
  latencyMs: number;
}
