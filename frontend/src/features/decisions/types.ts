// frontend\src\features\decisions\types.ts
import type { LucideIcon } from "lucide-react";

export type FlowStepStatus = "pending" | "running" | "done";

export interface FlowStep {
  id: string;
  title: string;
  icon: LucideIcon;
  status: FlowStepStatus;
  summary: string;
  details?: FlowStepDetail[];
}

export interface FlowStepDetail {
  label: string;
  value: string;
  tone?: "default" | "good" | "warn" | "bad" | "accent";
  mono?: boolean;
}

// ─────────────────────────────────────────────────────────────────────
// Run model — the graph the run view renders.
//
// One `RunNode` per stage the engine actually went through, plus the four
// routing outcomes and whatever followed the chosen one. Node state is
// derived from persisted rows (decision_log, execution_log,
// escalations, shadow_records, notifications) — never invented.
// ─────────────────────────────────────────────────────────────────────

export type RunNodeState =
  | "pending" // not reached yet
  | "active" // the step the engine is on right now
  | "success" // completed successfully
  | "shadow" // evaluated but deliberately not acted on
  | "blocked" // vetoed (validation or guardrail)
  | "escalated" // handed to a human, awaiting reply
  | "failed" // attempted and failed
  | "skipped"; // branch not taken

export type RunEdgeState = "done" | "active" | "skipped" | "failed";

export type RunNodeKind = "step" | "branch" | "terminal";

export type BadgeTone = "default" | "good" | "warn" | "bad" | "accent";

export interface RunBadge {
  label: string;
  tone: BadgeTone;
}

/** A notification that belongs to one node: a decision email or an escalation attempt. */
export interface RunNotification {
  id: string;
  nodeId: string;
  source: "email" | "escalation";
  /** ANOMALY_DETECTED / DECISION_MADE / ATTEMPT_1 / ATTEMPT_2 / ATTEMPT_3 */
  kind: string;
  subject: string;
  /** SENT / FAILED / SKIPPED / PENDING */
  status: string;
  at: string | null;
  error?: string | null;
  attempt?: number;
  recipient?: string;
}

export interface RunNode {
  id: string;
  kind: RunNodeKind;
  /** Report section this stage implements, e.g. "§3.7". */
  stage: string;
  title: string;
  subtitle: string;
  state: RunNodeState;
  icon: LucideIcon;
  durationMs: number | null;
  /** True when durationMs is a real measurement, false when it is a span or unknown. */
  measured: boolean;
  badges: RunBadge[];
  /** One extra line shown under the title in the inspector. */
  note?: string;
  notifications: RunNotification[];
  details: FlowStepDetail[];
  x: number;
  y: number;
  w: number;
  h: number;
  /** The step the engine will (or would) reach next. */
  isNext: boolean;
}

export interface RunEdge {
  id: string;
  from: string;
  to: string;
  /** SVG path data, already laid out in canvas coordinates. */
  d: string;
  state: RunEdgeState;
  label?: string;
  labelX?: number;
  labelY?: number;
  /** Draw a downward arrowhead at the end of the path. */
  arrow: boolean;
}

export interface RunSummary {
  outcome: string;
  outcomeLabel: string;
  outcomeState: RunNodeState;
  action: string;
  severityLabel: string;
  detectionConf: number;
  ruleConf: number;
  finalConf: number;
  risk: string;
  /** anomaly.detected_at → decision.created_at */
  totalMs: number | null;
  /** Sum of the instrumented compute stages. */
  computeMs: number | null;
  /** totalMs − computeMs: time the anomaly sat in the queue before the pipeline picked it up. */
  queueMs: number | null;
  currentStepId: string | null;
  nextStepId: string | null;
  failedStepIds: string[];
  notifications: RunNotification[];
  executionStatus: string | null;
  escalationStatus: string | null;
  shadowVerdict: string | null;
  guardrails: {
    /** True when the AUTO_EXECUTE gate actually ran (or vetoed). */
    checked: boolean;
    allowed: boolean;
    reason: string;
  };
}

export interface DecisionRun {
  nodes: RunNode[];
  edges: RunEdge[];
  width: number;
  height: number;
  summary: RunSummary;
  /** Which side tables actually had rows for this decision. */
  sources: {
    anomaly: boolean;
    executions: number;
    escalations: number;
    shadows: number;
    notifications: number;
  };
}
