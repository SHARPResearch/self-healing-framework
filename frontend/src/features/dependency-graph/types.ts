import type { Severity } from "@/shared/types";

/**
 * A node is one Kubernetes Deployment in the selfheal-apps namespace.
 * An edge A -> B means "A calls B", so B is A's upstream -- built from the
 * selfheal.io/upstreams annotation in the real system (Doc1 §5).
 */
export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphNodeInput {
  serviceId: string;
  displayName: string;
  status: Severity;
  anomalyScore: number;
  lastAction: string | null;
}
