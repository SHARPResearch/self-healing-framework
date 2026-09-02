import { recentIncidents, services } from "@/features/dashboard/data/mockData";
import { graphEdges, graphNodes } from "@/features/dependency-graph/data/mockData";
import { identifyRootCause } from "@/features/dependency-graph/lib/identifyRootCause";
import { rankActions } from "@/shared/lib/policyActions";

// The one critical incident already in the app's mock data -- every command
// below reasons about this same incident so the demo stays internally
// consistent instead of inventing a second, disconnected scenario.
const CRITICAL_INCIDENT = recentIncidents[0];
const CRITICAL_SERVICE = services.find((s) => s.serviceId === CRITICAL_INCIDENT.serviceId)!;

const SIMULATED_CAPTION = "_Simulated response — no LLM backend is wired up yet._";

function rootCauseFinding() {
  const result = identifyRootCause(CRITICAL_SERVICE.serviceId, graphNodes, graphEdges);
  const rootNode = graphNodes.find((n) => n.serviceId === result.rootCauseId)!;
  return { ...result, rootNode };
}

function buildSummarizeResponse(): string[] {
  const rc = rootCauseFinding();
  return [
    `## Incident summary\n${CRITICAL_SERVICE.displayName} crossed the critical anomaly threshold (score ${CRITICAL_SERVICE.anomalyScore.toFixed(2)}, threshold >0.85) at ${new Date(CRITICAL_INCIDENT.timestamp).toLocaleString()}.`,
    `## Timeline\n- 03:55 — score crossed 0.5, decision engine pre-warmed a replica\n- 05:42 — orders-service degraded, traffic shifted 50%\n- 06:05 — ${CRITICAL_SERVICE.displayName} hit ${CRITICAL_SERVICE.anomalyScore.toFixed(2)}, decision engine executed "${CRITICAL_INCIDENT.actionType}"`,
    `## Root cause\n${
      rc.isRootCause
        ? `${rc.rootNode.displayName} has no unhealthy dependency of its own — it is the primary root cause, not a cascading symptom.`
        : `${rc.rootNode.displayName} is the likely root cause. ${CRITICAL_SERVICE.displayName} calls it directly, so its elevated score is a cascading symptom rather than an independent failure.`
    }`,
    `## Impact\nServices that call ${CRITICAL_SERVICE.displayName} directly were at risk of cascading failure while traffic was drained — see the dependency graph for the full call chain.`,
    `## Remediation\n- Action taken: ${CRITICAL_INCIDENT.actionType}\n- Executor: ${CRITICAL_INCIDENT.executor}\n- Detail: ${CRITICAL_INCIDENT.details}`,
    `## Follow-ups\n- Confirm per-entity threshold calibration (ml-pipeline/calibrate.py) would have caught this earlier\n- Watch orders-service, which calls this service directly, for recurrence`,
    SIMULATED_CAPTION,
  ];
}

function buildRcaResponse(): string[] {
  const rc = rootCauseFinding();
  return [
    `## Root cause analysis: ${CRITICAL_SERVICE.displayName}`,
    rc.isRootCause
      ? `${CRITICAL_SERVICE.displayName} (score ${CRITICAL_SERVICE.anomalyScore.toFixed(2)}) has no unhealthy dependency it calls — it is the root cause itself, not downstream of another failing service.`
      : `${CRITICAL_SERVICE.displayName} calls ${rc.rootNode.displayName}, which is also unhealthy (${rc.rootNode.status}). ${rc.rootNode.displayName} is the likely root cause; ${CRITICAL_SERVICE.displayName}'s elevated score is a cascading symptom of it.`,
    SIMULATED_CAPTION,
  ];
}

function buildExplainResponse(): string[] {
  return [
    `## Why ${CRITICAL_SERVICE.displayName} was flagged`,
    `Its anomaly score reached ${CRITICAL_SERVICE.anomalyScore.toFixed(2)}. This project's severity thresholds are: below 0.5 watch, 0.5–0.7 warn, 0.7–0.85 degrade, and above 0.85 critical. ${CRITICAL_SERVICE.anomalyScore.toFixed(2)} crossed the 0.85 critical line, which is what triggered the decision engine to act automatically instead of just alerting.`,
    SIMULATED_CAPTION,
  ];
}

function buildRemediateResponse(): string[] {
  const actions = rankActions(CRITICAL_SERVICE);
  return [
    `## Suggested remediation for ${CRITICAL_SERVICE.displayName}\n${actions
      .map((a) => `- ${a.label} (confidence ${Math.round(a.confidence * 100)}%)`)
      .join("\n")}`,
    `Same ranking the Simulate Anomaly flow on Dashboard/Incidents uses, so recommendations stay consistent across the app.`,
    SIMULATED_CAPTION,
  ];
}

function buildFallbackResponse(): string[] {
  return [
    `I can help investigate incidents, explain anomaly scores, or suggest remediation. Try one of the commands below, or type /rca, /explain, /remediate, or /summarize.`,
    SIMULATED_CAPTION,
  ];
}

export function getMockResponse(input: string): string[] {
  const q = input.trim().toLowerCase();
  if (q.startsWith("/summarize") || q.includes("summarize incident")) return buildSummarizeResponse();
  if (q.startsWith("/rca") || q.includes("root cause analysis")) return buildRcaResponse();
  if (q.startsWith("/explain") || q.includes("explain alert")) return buildExplainResponse();
  if (q.startsWith("/remediate") || q.includes("suggest remediation")) return buildRemediateResponse();
  return buildFallbackResponse();
}
