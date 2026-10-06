import type { ServiceHealth } from "@/features/dashboard/types";

export interface PolicyAction {
  label: string;
  confidence: number;
}

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n));
}

/**
 * Ranks graduated remediation actions for a service by severity, using the
 * exact action vocabulary already established elsewhere in this app
 * (dashboard/data/mockData.ts's recentIncidents, ServiceManagementTable's row
 * actions) so every "what would the decision engine do" surface in the app
 * agrees. Confidence is a deterministic function of anomalyScore, not
 * Math.random() -- matches the graph layout / incident trend chart precedent
 * of avoiding non-determinism in anything that renders.
 *
 * This illustrates the *intended* behavior of the RL-based adaptive decision
 * engine (Doc1's Component 4) -- adaptive-pipeline/ is scaffold-only with no
 * trained model yet (see root CLAUDE.md), so this is a rule-based stand-in,
 * not a real policy inference.
 */
export function rankActions(service: ServiceHealth): PolicyAction[] {
  const s = service.anomalyScore;

  switch (service.status) {
    case "critical":
      return [
        { label: "Restart + rollback", confidence: clamp(0.55 + s * 0.42, 0, 0.98) },
        { label: "Shift traffic 100%", confidence: clamp(0.4 + s * 0.35, 0, 0.88) },
      ];
    case "degrade":
      return [
        { label: "Traffic shift 50%", confidence: clamp(0.5 + s * 0.4, 0, 0.92) },
        { label: "Scale +1 replica", confidence: clamp(0.35 + s * 0.35, 0, 0.8) },
      ];
    case "warn":
      return [
        { label: "Scale +1 replica", confidence: clamp(0.45 + s * 0.4, 0, 0.88) },
        { label: "Pre-warm replica", confidence: clamp(0.3 + s * 0.3, 0, 0.72) },
      ];
    default:
      return [{ label: "Continue monitoring", confidence: 0.99 }];
  }
}
