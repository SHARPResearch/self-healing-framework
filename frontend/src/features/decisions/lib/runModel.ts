// frontend\src\features\decisions\lib\runModel.ts
//
// Turns persisted rows into the decision-run graph. Pure: no fetching, no
// React, no side effects — so the whole derivation is unit-testable and the
// diagram component stays dumb.
//
// Every state and duration here comes from a row that exists in the DB.
// When a stage has no instrumentation (decisions persisted before
// `decision_log.context.timings` was written) the node reports
// `durationMs: null` and the UI shows "—" instead of a guess.
import {
  Bell,
  CheckCircle2,
  Eye,
  Gauge,
  GitBranch,
  ListChecks,
  Mail,
  Radio,
  ShieldCheck,
  Target,
  UserCheck,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";
import type {
  ApiAnomalyDecisionRow,
  ApiDbAnomaly,
  ApiDecision,
  ApiEscalationAttempt,
  ApiEscalationRow,
  ApiExecutionRow,
  ApiNotificationEntry,
  ApiShadowRow,
} from "@/lib/api";
import type {
  DecisionRun,
  FlowStepDetail,
  RunBadge,
  RunEdge,
  RunEdgeState,
  RunNode,
  RunNodeKind,
  RunNodeState,
  RunNotification,
  RunSummary,
} from "../types";
import { detailsFor } from "./steps";
import { formatClock, formatDuration, spanMs } from "./format";
import { asJson } from "./json";

// ── Canvas geometry ────────────────────────────────────────────────
// Fixed coordinates, laid out once here rather than measured at runtime.
// The diagram scales the whole canvas with a viewBox, so these numbers are
// "design pixels" and never need to match the rendered size.
const W = 900;
const NODE_W = 200;
const NODE_H = 76;
const TERM_H = 54;
const SPINE_CX = 450;
const TOP = 18;
const PITCH = 100;
const BUS_Y = 628;
const BRANCH_Y = 654;
const CONT_Y = 764;
const CONT2_Y = 864;
const H = 958;

const COL = { block: 120, shadow: 340, human: 560, auto: 780 } as const;

const SPINE_IDS = [
  "input",
  "context",
  "rules",
  "severity_action",
  "validation",
  "guardrails",
] as const;

interface NodeSpec {
  id: string;
  kind: RunNodeKind;
  stage: string;
  title: string;
  subtitle: string;
  state: RunNodeState;
  icon: RunNode["icon"];
  x: number;
  y: number;
  h?: number;
  durationMs?: number | null;
  measured?: boolean;
  badges?: RunBadge[];
  note?: string;
  details?: FlowStepDetail[];
  isNext?: boolean;
}

function mkNode(s: NodeSpec): RunNode {
  return {
    id: s.id,
    kind: s.kind,
    stage: s.stage,
    title: s.title,
    subtitle: s.subtitle,
    state: s.state,
    icon: s.icon,
    durationMs: s.durationMs ?? null,
    measured: s.measured ?? false,
    badges: s.badges ?? [],
    note: s.note,
    notifications: [],
    details: s.details ?? [],
    x: s.x,
    y: s.y,
    w: NODE_W,
    h: s.h ?? NODE_H,
    isNext: s.isNext ?? false,
  };
}

function spineX() {
  return SPINE_CX - NODE_W / 2;
}

function colX(cx: number) {
  return cx - NODE_W / 2;
}

// ── Small helpers ──────────────────────────────────────────────────
function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function clip(text: string, max = 52): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Sum the timing keys that are actually present; null when none are. */
function timingSum(
  timings: Record<string, number> | null | undefined,
  keys: string[],
): number | null {
  if (!timings) return null;
  let seen = false;
  let total = 0;
  for (const key of keys) {
    const value = timings[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      seen = true;
      total += value;
    }
  }
  return seen ? total : null;
}

const OUTCOME_LABEL: Record<string, string> = {
  AUTO_EXECUTE: "Auto-execute",
  SHADOW_MODE: "Shadow mode",
  HUMAN_LOOP: "Human in the loop",
  BLOCK: "Blocked",
  NO_RULE_MATCHED: "No rule matched",
  UNVALIDATED: "Unvalidated",
  PENDING_VALIDATION: "Pending validation",
};

const OUTCOME_STATE: Record<string, RunNodeState> = {
  AUTO_EXECUTE: "success",
  SHADOW_MODE: "shadow",
  HUMAN_LOOP: "escalated",
  BLOCK: "blocked",
};

function execState(status: string): RunNodeState {
  switch (status) {
    case "SUCCESS":
      return "success";
    case "FAILED":
      return "failed";
    case "DRY_RUN":
      return "shadow";
    case "NOT_IMPLEMENTED":
    case "SKIPPED":
      return "skipped";
    default:
      return "pending";
  }
}

function escalationState(status: string): RunNodeState {
  switch (status) {
    case "RESOLVED":
      return "success";
    case "MANUAL_REQUIRED":
      return "failed";
    case "AWAITING_HUMAN":
    case "PENDING":
      return "escalated";
    default:
      return "escalated";
  }
}

// ── Builder ────────────────────────────────────────────────────────
export interface RunSources {
  decision: ApiDecision;
  anomaly: ApiDbAnomaly | ApiAnomalyDecisionRow | null;
  executions: ApiExecutionRow[];
  escalations: ApiEscalationRow[];
  shadows: ApiShadowRow[];
  notifications: ApiNotificationEntry[];
}

export function buildDecisionRun(src: RunSources): DecisionRun {
  const { decision: d, anomaly } = src;

  const exec = src.executions.find((e) => e.decision_id === d.decision_id) ?? null;
  const esc =
    src.escalations.find((e) => e.decision_id === d.decision_id) ?? null;
  const shadow = src.shadows.find((s) => s.decision_id === d.decision_id) ?? null;

  // JSONB columns arrive encoded — decode once, use everywhere below.
  const escAttempts = asJson<ApiEscalationAttempt[]>(esc?.notifications, []);
  const escResponse = asJson<{
    decision?: string;
    by?: string;
    at?: string;
    note?: string;
  }>(esc?.response, {});

  const outcome = String(d.policy?.outcome ?? "UNVALIDATED").toUpperCase();
  const reason = d.policy?.reason ?? "";
  const taken = Boolean(OUTCOME_STATE[outcome]);
  const ruleMatched = Boolean(d.rule_id);
  const guardrailBlocked = outcome === "BLOCK" && /guardrail/i.test(reason);

  const timings =
    d.timings ??
    ((d.context as unknown as { timings?: Record<string, number> })?.timings ?? null);

  const contextMs = timingSum(timings, ["context_ms"]);
  const rulesMs = timingSum(timings, ["classify_ms", "rules_ms"]);
  const severityActionMs = timingSum(timings, ["severity_ms", "selection_ms"]);
  const validationMs = timingSum(timings, ["validation_ms"]);
  const guardrailsMs = timingSum(timings, ["guardrails_ms"]);
  const queueMsTimed = timingSum(timings, ["queue_ms"]);

  const totalMs = spanMs(anomaly?.detected_at, d.created_at);
  const computeMs = timingSum(timings, [
    "context_ms",
    "classify_ms",
    "rules_ms",
    "severity_ms",
    "selection_ms",
    "validation_ms",
    "guardrails_ms",
    "persist_ms",
  ]);
  const queueMs =
    totalMs !== null && computeMs !== null
      ? Math.max(0, totalMs - computeMs)
      : queueMsTimed;

  const execMs = exec ? spanMs(d.created_at, exec.executed_at) : null;
  const escMs = esc ? spanMs(d.created_at, esc.created_at) : null;

  const upstream = d.context?.upstream ?? [];
  const downstream = d.context?.downstream ?? [];
  const blast = d.context?.blast_members ?? [];
  const selectedGuardrails = (
    d.selection?.selected as { guardrails?: Record<string, unknown> } | undefined
  )?.guardrails;

  // Component 1 provenance: the detector's model version, drift phase and the
  // provenance of the telemetry that fed the context. Absent on older rows.
  const c1 = (d.component1 ?? {}) as Record<string, unknown>;
  const telemetrySource = (c1.telemetry_source ?? null) as {
    infra?: string;
    app?: string;
  } | null;

  const execStat = exec?.status ?? "";
  const escStat = esc?.status ?? "";
  const finished =
    Boolean(exec) ||
    escStat === "RESOLVED" ||
    escStat === "MANUAL_REQUIRED" ||
    ["BLOCK", "SHADOW_MODE", "NO_RULE_MATCHED"].includes(outcome);

  // ── Which node is the engine on, and what comes next? ────────────
  let activeId: string | null = null;
  if (outcome === "UNVALIDATED" || outcome === "PENDING_VALIDATION") {
    activeId = "validation";
  } else if (outcome === "AUTO_EXECUTE" && !exec) {
    activeId = "execution";
  } else if (outcome === "HUMAN_LOOP" && (!esc || escStat === "PENDING")) {
    activeId = "escalation";
  }

  const nextMap: Record<string, string> = {
    validation: "guardrails",
    execution: "outcome",
    escalation: "human_decision",
  };
  const nextId = activeId ? nextMap[activeId] ?? null : null;

  const stateOr = (id: string, fallback: RunNodeState): RunNodeState =>
    id === activeId ? "active" : fallback;

  // ── Spine ────────────────────────────────────────────────────────
  const spineState = (id: string): RunNodeState => {
    switch (id) {
      case "input":
        return stateOr(id, "success");
      case "context":
        return stateOr(id, "success");
      case "rules":
        return stateOr(id, ruleMatched ? "success" : "blocked");
      case "severity_action":
        return stateOr(id, ruleMatched ? "success" : "skipped");
      case "validation": {
        if (outcome === "NO_RULE_MATCHED") return "skipped";
        if (outcome === "UNVALIDATED" || outcome === "PENDING_VALIDATION")
          return "active";
        return "success";
      }
      case "guardrails": {
        if (outcome === "NO_RULE_MATCHED") return "skipped";
        if (guardrailBlocked) return "blocked";
        if (outcome === "AUTO_EXECUTE") return "success";
        if (outcome === "UNVALIDATED" || outcome === "PENDING_VALIDATION")
          return "pending";
        return "skipped";
      }
      default:
        return "pending";
    }
  };

  const spine: RunNode[] = [
    mkNode({
      id: "input",
      kind: "step",
      stage: "§3.1",
      title: "Anomaly received",
      subtitle: `${formatClock(anomaly?.detected_at)} · ${clip(d.anomaly_id, 22)}`,
      state: spineState("input"),
      icon: Radio,
      x: spineX(),
      y: TOP,
      details: [
        { label: "Anomaly id", value: d.anomaly_id, mono: true },
        { label: "Service", value: d.service_id, mono: true },
        {
          label: "Detected at",
          value: anomaly?.detected_at ? formatClock(anomaly.detected_at) : "—",
          mono: true,
        },
        {
          label: "Anomaly score",
          value: anomaly ? num(anomaly.anomaly_score).toFixed(3) : "—",
          mono: true,
        },
        {
          label: "Severity band",
          value: anomaly?.severity?.toUpperCase() ?? "—",
          tone:
            anomaly?.severity === "high"
              ? "bad"
              : anomaly?.severity === "medium"
                ? "warn"
                : "good",
        },
        {
          label: "Evidence snapshot",
          value: anomaly?.snapshot_status ?? "—",
          mono: true,
          tone: anomaly?.snapshot_status === "failed" ? "bad" : "default",
        },
        // ── Component 1 (anomaly detector + dynamic model updating) ──
        ...(c1.model_version !== undefined && c1.model_version !== null
          ? [
              {
                label: "Detector model",
                value: `v${String(c1.model_version)}`,
                mono: true,
              },
            ]
          : []),
        ...(c1.phase
          ? [{ label: "Model phase", value: String(c1.phase), mono: true }]
          : []),
        ...(c1.drift_detected
          ? [
              {
                label: "Drift",
                value: c1.quarantine_trigger
                  ? `detected (${String(c1.quarantine_trigger)})`
                  : "detected",
                tone: "warn" as const,
              },
            ]
          : []),
        ...(typeof c1.open_queries === "number"
          ? [
              {
                label: "Open operator queries",
                value: String(c1.open_queries),
                mono: true,
              },
            ]
          : []),
        ...(telemetrySource
          ? [
              {
                label: "Telemetry used",
                value: `infra ${telemetrySource.infra} · app ${telemetrySource.app}`,
              },
            ]
          : []),
      ],
      badges:
        c1.model_version !== undefined && c1.model_version !== null
          ? [{ label: `C1 v${String(c1.model_version)}`, tone: "accent" as const }]
          : [],
    }),
    mkNode({
      id: "context",
      kind: "step",
      stage: "§3.2",
      title: "Graph context",
      subtitle: `${upstream.length} up · ${downstream.length} down · blast ${blast.length}`,
      state: spineState("context"),
      icon: GitBranch,
      x: spineX(),
      y: TOP + PITCH,
      durationMs: contextMs,
      measured: contextMs !== null,
      details: [
        ...detailsFor("context", d),
        ...detailsFor("cascade", d).map((row) => ({ ...row, label: `Cascade ${row.label.toLowerCase()}` })),
      ],
    }),
    mkNode({
      id: "rules",
      kind: "step",
      stage: "§3.3",
      title: "Rule evaluation",
      subtitle: ruleMatched
        ? clip(d.rule_id ?? "", 34)
        : "no rule fired for this context",
      state: spineState("rules"),
      icon: Target,
      x: spineX(),
      y: TOP + PITCH * 2,
      durationMs: rulesMs,
      measured: rulesMs !== null,
      badges:
        (d.selection?.rejected?.length ?? 0) > 0
          ? [
              {
                label: `${d.selection?.rejected?.length} rejected`,
                tone: "warn",
              },
            ]
          : [],
      details: detailsFor("rules", d),
    }),
    mkNode({
      id: "severity_action",
      kind: "step",
      stage: "§3.4",
      title: "Severity & action",
      subtitle: `${d.severity?.label ?? "—"} · ${clip(d.action, 22)}`,
      state: spineState("severity_action"),
      icon: Gauge,
      x: spineX(),
      y: TOP + PITCH * 3,
      durationMs: severityActionMs,
      measured: severityActionMs !== null,
      details: [
        { label: "Selected action", value: d.action, mono: true, tone: "accent" },
        { label: "Action params", value: JSON.stringify(d.action_params ?? {}), mono: true },
        ...detailsFor("severity", d),
      ],
    }),
    mkNode({
      id: "validation",
      kind: "step",
      stage: "§3.6",
      title: "Safety validation",
      subtitle: `conf ${pct(num(d.confidence?.final))} · risk ${d.base_risk}`,
      state: spineState("validation"),
      icon: ShieldCheck,
      x: spineX(),
      y: TOP + PITCH * 4,
      durationMs: validationMs,
      measured: validationMs !== null,
      badges: [
        {
          label: OUTCOME_LABEL[outcome] ?? outcome,
          tone:
            outcome === "AUTO_EXECUTE"
              ? "good"
              : outcome === "SHADOW_MODE"
                ? "accent"
                : outcome === "HUMAN_LOOP"
                  ? "warn"
                  : outcome === "BLOCK" || outcome === "NO_RULE_MATCHED"
                    ? "bad"
                    : "default",
        },
      ],
      note: reason || undefined,
      details: [
        ...detailsFor("decision", d),
        { label: "Policy reason", value: reason || "—" },
      ],
    }),
    mkNode({
      id: "guardrails",
      kind: "step",
      stage: "§3.7",
      title: "Safety guardrails",
      subtitle: guardrailBlocked
        ? "vetoed the action"
        : outcome === "AUTO_EXECUTE"
          ? "cooldown · counter · idempotency"
          : "not required for this outcome",
      state: spineState("guardrails"),
      icon: ListChecks,
      x: spineX(),
      y: TOP + PITCH * 5,
      durationMs: guardrailsMs,
      measured: guardrailsMs !== null,
      badges: guardrailBlocked
        ? [{ label: "blocked", tone: "bad" }]
        : outcome === "AUTO_EXECUTE"
          ? [{ label: "passed", tone: "good" }]
          : [{ label: "skipped", tone: "default" }],
      note: guardrailBlocked ? reason : undefined,
      details: [
        {
          label: "Cooldown",
          value: selectedGuardrails?.cooldown_seconds
            ? `${selectedGuardrails.cooldown_seconds}s`
            : "—",
          mono: true,
        },
        {
          label: "Max per hour",
          value: selectedGuardrails?.max_per_hour
            ? String(selectedGuardrails.max_per_hour)
            : "—",
          mono: true,
        },
        {
          label: "Idempotency key",
          value: String(selectedGuardrails?.idempotency_key ?? "default template"),
          mono: true,
        },
        {
          label: "Verdict",
          value: guardrailBlocked
            ? "blocked"
            : outcome === "AUTO_EXECUTE"
              ? "allowed"
              : "not evaluated",
          tone: guardrailBlocked ? "bad" : outcome === "AUTO_EXECUTE" ? "good" : "default",
        },
        { label: "Gate time", value: formatDuration(guardrailsMs), mono: true },
      ],
    }),
  ];

  // ── Branch row ───────────────────────────────────────────────────
  const branch = (
    id: string,
    col: number,
    spec: Omit<NodeSpec, "x" | "y" | "kind" | "id">,
  ): RunNode =>
    mkNode({
      ...spec,
      id,
      kind: "branch",
      x: colX(col),
      y: BRANCH_Y,
    });

  const branchNodes: RunNode[] = [
    branch("block", COL.block, {
      stage: "§3.6",
      title: "BLOCK",
      subtitle: guardrailBlocked ? "guardrail veto" : "safety veto",
      state: taken
        ? outcome === "BLOCK"
          ? "blocked"
          : "skipped"
        : "skipped",
      icon: XCircle,
      badges:
        outcome === "BLOCK"
          ? [{ label: guardrailBlocked ? "guardrail" : "validation", tone: "bad" }]
          : [],
      note: outcome === "BLOCK" ? reason || undefined : undefined,
      details: [
        { label: "Outcome", value: "BLOCK", mono: true, tone: "bad" },
        { label: "Reason", value: outcome === "BLOCK" ? reason || "—" : "not taken" },
        { label: "Side effects", value: "none — decision_log is the record" },
      ],
    }),
    branch("shadow", COL.shadow, {
      stage: "§4.4",
      title: "SHADOW",
      subtitle: shadow ? `verdict ${shadow.verdict ?? "pending"}` : "observe only",
      state: taken
        ? outcome === "SHADOW_MODE"
          ? "shadow"
          : "skipped"
        : "skipped",
      icon: Eye,
      badges:
        outcome === "SHADOW_MODE"
          ? [{ label: "no execution", tone: "accent" }]
          : [],
      details: [
        { label: "Outcome", value: "SHADOW_MODE", mono: true, tone: "accent" },
        {
          label: "Candidate action",
          value: shadow?.candidate_action ?? "—",
          mono: true,
        },
        { label: "Verdict", value: shadow?.verdict ?? "not yet observed" },
        { label: "Learning", value: shadow?.learning ?? "—" },
      ],
    }),
    branch("human", COL.human, {
      stage: "§3.8",
      title: "HUMAN LOOP",
      subtitle: esc ? `${esc.attempt}/${esc.max_attempts} attempts` : "asks a human",
      state: taken
        ? outcome === "HUMAN_LOOP"
          ? "escalated"
          : "skipped"
        : "skipped",
      icon: Bell,
      badges:
        outcome === "HUMAN_LOOP"
          ? [{ label: "approval needed", tone: "warn" }]
          : [],
      details: [
        { label: "Outcome", value: "HUMAN_LOOP", mono: true, tone: "warn" },
        { label: "Escalation id", value: esc?.id ?? "—", mono: true },
        { label: "Status", value: esc?.status ?? "not created" },
        { label: "Operator", value: escResponse.by ?? "—", mono: true },
      ],
    }),
    branch("auto", COL.auto, {
      stage: "§3.6",
      title: "AUTO EXECUTE",
      subtitle: "confidence high · risk low",
      state: taken
        ? outcome === "AUTO_EXECUTE"
          ? "success"
          : "skipped"
        : "skipped",
      icon: Zap,
      badges:
        outcome === "AUTO_EXECUTE" ? [{ label: "gate passed", tone: "good" }] : [],
      details: [
        { label: "Outcome", value: "AUTO_EXECUTE", mono: true, tone: "good" },
        {
          label: "Final confidence",
          value: pct(num(d.confidence?.final)),
          mono: true,
        },
        { label: "Risk band", value: d.base_risk, mono: true },
      ],
    }),
  ];

  // ── Continuations ────────────────────────────────────────────────
  // An execution row on a non-AUTO decision means an operator approved the
  // escalation and the approval path ran the executor.
  const approvedExecution = Boolean(exec) && outcome !== "AUTO_EXECUTE";

  const execNode = mkNode({
    id: "execution",
    kind: "step",
    stage: "§5.5",
    title: "Executor",
    subtitle: exec
      ? approvedExecution
        ? `${exec.status} · approved`
        : exec.status
      : outcome === "AUTO_EXECUTE"
        ? "queued"
        : "not reached",
    state: exec
      ? execState(execStat)
      : outcome === "AUTO_EXECUTE"
        ? "active"
        : "skipped",
    icon: Wrench,
    x: colX(COL.auto),
    y: CONT_Y,
    durationMs: execMs,
    measured: execMs !== null,
    badges: exec
      ? [
          { label: exec.status, tone: badgeToneForExec(execStat) },
          ...(approvedExecution
            ? [{ label: "approved", tone: "accent" as const }]
            : []),
        ]
      : [],
    note: exec?.message ?? undefined,
    details: exec
      ? [
          { label: "Execution id", value: String(exec.id), mono: true },
          { label: "Status", value: exec.status, mono: true },
          { label: "Action", value: exec.action, mono: true },
          {
            label: "Trigger",
            value: approvedExecution ? "operator approval" : "AUTO_EXECUTE policy",
          },
          { label: "Message", value: exec.message ?? "—" },
          {
            label: "Executed at",
            value: exec.executed_at ? formatClock(exec.executed_at) : "—",
            mono: true,
          },
          { label: "Latency", value: formatDuration(execMs), mono: true },
        ]
      : [
          { label: "Status", value: "no execution row yet", tone: "warn" },
          {
            label: "Executor",
            value:
              "dry-run (KUBERNETES_DRY_RUN=1) returns NOT_IMPLEMENTED but still logs",
          },
        ],
  });

  const doneNode = mkNode({
    id: "outcome",
    kind: "terminal",
    stage: "§8.2",
    title: execStat === "SUCCESS" ? "Recovered" : execStat === "FAILED" ? "Recovery failed" : "Action dispatched",
    subtitle: exec ? clip(exec.message ?? exec.status, 40) : "awaiting executor",
    state: exec
      ? execState(execStat)
      : outcome === "AUTO_EXECUTE"
        ? "pending"
        : "skipped",
    icon: execStat === "FAILED" ? XCircle : CheckCircle2,
    x: colX(COL.auto),
    y: CONT2_Y,
    badges: exec ? [{ label: exec.status, tone: badgeToneForExec(execStat) }] : [],
    details: [
      { label: "Action", value: d.action, mono: true },
      { label: "Result", value: exec?.status ?? "pending", mono: true },
      { label: "Total run", value: formatDuration(totalMs), mono: true },
    ],
  });

  const escalationNode = mkNode({
    id: "escalation",
    kind: "step",
    stage: "§3.8",
    title: "Escalation · 3 attempts",
    subtitle: esc
      ? `attempt ${esc.attempt}/${esc.max_attempts} · ${esc.status}`
      : "not created",
    state: outcome === "HUMAN_LOOP" ? escalationState(escStat || "PENDING") : "skipped",
    icon: Mail,
    x: colX(COL.human),
    y: CONT_Y,
    durationMs: escMs,
    measured: escMs !== null,
    badges: esc
      ? [{ label: `${esc.attempt}/${esc.max_attempts}`, tone: escStat === "MANUAL_REQUIRED" ? "bad" : "warn" }]
      : [],
    note: esc?.failure_report ?? undefined,
    details: esc
      ? [
          { label: "Escalation id", value: esc.id, mono: true },
          { label: "Status", value: esc.status, mono: true },
          { label: "Attempts", value: `${esc.attempt} of ${esc.max_attempts}`, mono: true },
          {
            label: "Next attempt",
            value: esc.next_attempt_at ? formatClock(esc.next_attempt_at) : "—",
            mono: true,
          },
          { label: "Handoff latency", value: formatDuration(escMs), mono: true },
          { label: "Failure report", value: esc.failure_report ?? "—" },
        ]
      : [
          { label: "Status", value: "no escalation row", tone: "warn" },
          { label: "Notes", value: "HUMAN_LOOP creates one via escalate()" },
        ],
  });

  const humanDecisionNode = mkNode({
    id: "human_decision",
    kind: "terminal",
    stage: "§3.8",
    title:
      escStat === "RESOLVED"
        ? `Operator ${escResponse.decision ?? "resolved"}`
        : escStat === "MANUAL_REQUIRED"
          ? "Manual intervention"
          : "Awaiting operator",
    subtitle:
      escStat === "RESOLVED"
        ? clip(escResponse.by ?? "operator", 30)
        : escStat === "MANUAL_REQUIRED"
          ? "3 attempts exhausted"
          : "schedule: T+0 · T+5m · T+15m",
    state:
      outcome === "HUMAN_LOOP"
        ? escStat
          ? escalationState(escStat)
          : "escalated"
        : "skipped",
    icon: UserCheck,
    x: colX(COL.human),
    y: CONT2_Y,
    badges: escStat ? [{ label: escStat, tone: escStat === "RESOLVED" ? "good" : "warn" }] : [],
    details: [
      { label: "Status", value: escStat || "—" },
      {
        label: "Answered by",
        value: escResponse.by ?? "—",
        mono: true,
      },
      { label: "At", value: escResponse.at ? formatClock(escResponse.at) : "—", mono: true },
      { label: "Note", value: escResponse.note || "—" },
    ],
  });

  const blockTerm = mkNode({
    id: "block_terminal",
    kind: "terminal",
    stage: "§3.6",
    title: "No action taken",
    subtitle: "logged only",
    state: outcome === "BLOCK" ? "blocked" : "skipped",
    icon: XCircle,
    x: colX(COL.block),
    y: CONT_Y,
    h: TERM_H,
    details: [
      { label: "Executed", value: "no" },
      { label: "Recorded in", value: "decision_log", mono: true },
    ],
  });

  const shadowTerm = mkNode({
    id: "shadow_terminal",
    kind: "terminal",
    stage: "§4.4",
    title: "Counterfactual logged",
    subtitle: shadow ? `verdict ${shadow.verdict ?? "pending"}` : "shadow_records",
    state: outcome === "SHADOW_MODE" ? "shadow" : "skipped",
    icon: Eye,
    x: colX(COL.shadow),
    y: CONT_Y,
    h: TERM_H,
    details: [
      { label: "Executed", value: "no — observed only" },
      { label: "Recorded in", value: "shadow_records", mono: true },
      { label: "Verdict", value: shadow?.verdict ?? "pending observation" },
    ],
  });

  const nodes: RunNode[] = [
    ...spine,
    ...branchNodes,
    escalationNode,
    humanDecisionNode,
    execNode,
    doneNode,
    blockTerm,
    shadowTerm,
  ];

  // ── Next-step marking ────────────────────────────────────────────
  if (nextId) {
    const target = nodes.find((n) => n.id === nextId);
    if (target) target.isNext = true;
  }

  // ── Notifications ────────────────────────────────────────────────
  const runNotifications: RunNotification[] = [];

  for (const entry of src.notifications) {
    if (entry.decision_id !== d.decision_id) continue;
    const kind = String(entry.kind ?? "NOTIFICATION");
    const nodeId =
      kind === "ANOMALY_DETECTED"
        ? "input"
        : outcome === "HUMAN_LOOP"
          ? "escalation"
          : outcome === "AUTO_EXECUTE"
            ? "execution"
            : "validation";
    runNotifications.push({
      id: entry.id,
      nodeId,
      source: "email",
      kind,
      subject: entry.subject,
      status: entry.status,
      at: entry.sent_at ?? entry.created_at,
      error: entry.error,
      recipient: entry.recipient,
    });
  }

  if (esc && escAttempts.length) {
    for (const attempt of escAttempts) {
      runNotifications.push({
        id: `${esc.id}-a${attempt.attempt}`,
        nodeId: "escalation",
        source: "escalation",
        kind: `ATTEMPT_${attempt.attempt}`,
        subject: attempt.subject ?? `Escalation attempt ${attempt.attempt}`,
        status: attempt.sent ? "SENT" : attempt.error ? "FAILED" : "SKIPPED",
        at: attempt.sent_at,
        error: attempt.error ?? null,
        attempt: attempt.attempt,
      });
    }
  }

  // Newest first.
  runNotifications.sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""));

  for (const notification of runNotifications) {
    const node = nodes.find((n) => n.id === notification.nodeId);
    if (node) node.notifications.push(notification);
  }

  // ── Edges ────────────────────────────────────────────────────────
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const edges: RunEdge[] = [];

  const cxOf = (n: RunNode) => n.x + n.w / 2;
  const bottomOf = (n: RunNode) => n.y + n.h;

  const spineEdgeState = (target: RunNode): RunEdgeState =>
    target.state === "active"
      ? "active"
      : target.state === "pending"
        ? "skipped"
        : "done";

  for (let i = 0; i < SPINE_IDS.length - 1; i += 1) {
    const from = byId.get(SPINE_IDS[i]);
    const to = byId.get(SPINE_IDS[i + 1]);
    if (!from || !to) continue;
    const x = cxOf(from);
    edges.push({
      id: `${from.id}-${to.id}`,
      from: from.id,
      to: to.id,
      d: `M ${x} ${bottomOf(from)} L ${x} ${to.y}`,
      state: spineEdgeState(to),
      arrow: true,
      ...(from.id === "input" && queueMs !== null
        ? {
            label: `+${formatDuration(queueMs)} queued`,
            labelX: x + 8,
            labelY: (bottomOf(from) + to.y) / 2,
          }
        : {}),
    });
  }

  const guardrailsNode = byId.get("guardrails");
  const trunkState: RunEdgeState = taken
    ? "done"
    : activeId === "validation"
      ? "active"
      : "skipped";
  if (guardrailsNode) {
    const x = cxOf(guardrailsNode);
    edges.push({
      id: "trunk",
      from: "guardrails",
      to: "bus",
      d: `M ${x} ${bottomOf(guardrailsNode)} L ${x} ${BUS_Y}`,
      state: trunkState,
      arrow: true,
    });
  }
  edges.push({
    id: "bus",
    from: "bus",
    to: "bus",
    d: `M ${COL.block} ${BUS_Y} L ${COL.auto} ${BUS_Y}`,
    state: taken ? "done" : "skipped",
    arrow: false,
  });

  for (const b of branchNodes) {
    const x = cxOf(b);
    const isTaken = b.state !== "skipped";
    edges.push({
      id: `bus-${b.id}`,
      from: "bus",
      to: b.id,
      d: `M ${x} ${BUS_Y} L ${x} ${b.y}`,
      state: isTaken ? "done" : "skipped",
      arrow: true,
    });
  }

  const continues: Array<[string, string]> = [
    ["block", "block_terminal"],
    ["shadow", "shadow_terminal"],
    ["human", "escalation"],
    ["escalation", "human_decision"],
    ["auto", "execution"],
    ["execution", "outcome"],
  ];

  for (const [fromId, toId] of continues) {
    const from = byId.get(fromId);
    const to = byId.get(toId);
    if (!from || !to) continue;
    const x = cxOf(to);
    const state: RunEdgeState =
      to.state === "skipped" || to.state === "pending"
        ? "skipped"
        : to.state === "active"
          ? "active"
          : "done";
    edges.push({
      id: `${fromId}-${toId}`,
      from: fromId,
      to: toId,
      d: `M ${x} ${bottomOf(from)} L ${x} ${to.y}`,
      state,
      arrow: true,
    });
  }

  // ── Summary ──────────────────────────────────────────────────────
  const failedStepIds = nodes
    .filter((n) => n.state === "failed" || n.state === "blocked")
    .map((n) => n.id);

  const summary: RunSummary = {
    outcome,
    outcomeLabel: OUTCOME_LABEL[outcome] ?? outcome,
    outcomeState: OUTCOME_STATE[outcome] ?? "pending",
    action: d.action,
    severityLabel: d.severity?.label ?? "—",
    detectionConf: num(d.confidence?.detection),
    ruleConf: num(d.confidence?.rule),
    finalConf: num(d.confidence?.final),
    risk: d.base_risk ?? "—",
    totalMs,
    computeMs,
    queueMs,
    currentStepId: activeId ?? (finished ? null : "validation"),
    nextStepId: nextId,
    failedStepIds,
    notifications: runNotifications,
    executionStatus: exec?.status ?? null,
    escalationStatus: escStat || null,
    shadowVerdict: shadow?.verdict ?? null,
    guardrails: {
      checked: outcome === "AUTO_EXECUTE" || guardrailBlocked,
      allowed: !guardrailBlocked,
      reason: guardrailBlocked
        ? reason
        : outcome === "AUTO_EXECUTE"
          ? "all checks passed"
          : "not evaluated — only AUTO_EXECUTE is gated",
    },
  };

  return {
    nodes,
    edges,
    width: W,
    height: H,
    summary,
    sources: {
      anomaly: Boolean(anomaly),
      executions: src.executions.filter((e) => e.decision_id === d.decision_id).length,
      escalations: src.escalations.filter((e) => e.decision_id === d.decision_id).length,
      shadows: src.shadows.filter((s) => s.decision_id === d.decision_id).length,
      notifications: runNotifications.length,
    },
  };
}

function badgeToneForExec(status: string): RunBadge["tone"] {
  if (status === "SUCCESS") return "good";
  if (status === "FAILED") return "bad";
  if (status === "DRY_RUN") return "accent";
  if (status === "NOT_IMPLEMENTED" || status === "SKIPPED") return "warn";
  return "default";
}

/** Convenience for the legend/ordering used by tests and the inspector. */
export const RUN_STAGE_ORDER = SPINE_IDS;
