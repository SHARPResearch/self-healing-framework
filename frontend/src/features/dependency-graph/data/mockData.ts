import { services } from "@/features/dashboard/data/mockData";
import type { GraphEdge, GraphNodeInput } from "../types";

/**
 * Nodes reuse the dashboard's service array so severity and anomaly scores
 * stay identical to every other page.
 */
export const graphNodes: GraphNodeInput[] = services.map((s) => ({
  serviceId: s.serviceId,
  displayName: s.displayName,
  status: s.status,
  anomalyScore: s.anomalyScore,
  lastAction: s.lastAction,
}));

/**
 * Edge A -> B means "A calls B".
 *
 * The first four edges are the demo topology documented in
 * docs/Doc3_Execution_Guide.md. That topology only covers four of our six
 * services though, which would leave service-e-payments and service-f-search
 * as disconnected orphans -- and payments is the only critical service, so
 * neither the pulsing critical node nor the amber downstream-critical edge
 * would ever render. The last two edges are added here so the graph actually
 * exercises those states; they are plausible call paths (orders takes
 * payments, search reads inventory) rather than doc-sourced.
 */
export const graphEdges: GraphEdge[] = [
  { source: "service-b-orders", target: "service-a-auth", latencyMs: 14 },
  { source: "service-b-orders", target: "service-c-inventory", latencyMs: 22 },
  { source: "service-c-inventory", target: "service-a-auth", latencyMs: 9 },
  { source: "service-d-notification", target: "service-b-orders", latencyMs: 31 },
  { source: "service-b-orders", target: "service-e-payments", latencyMs: 18 },
  { source: "service-f-search", target: "service-c-inventory", latencyMs: 12 },
];
