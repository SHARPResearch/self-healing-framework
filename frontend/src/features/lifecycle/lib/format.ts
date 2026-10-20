import type { LifecycleAction, LifecyclePhase, OperatorQuery, Verdict } from "../types";

export type Tone = "neutral" | "info" | "good" | "warn" | "bad";

/** Tailwind classes per tone, on the existing status tokens (warn is blue, degrade amber). */
export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  info: "text-status-warn",
  good: "text-status-healthy",
  warn: "text-status-degrade",
  bad: "text-status-critical",
};

export const TONE_PILL: Record<Tone, string> = {
  neutral: "bg-muted text-muted-foreground",
  info: "bg-status-warn/15 text-status-warn",
  good: "bg-status-healthy/15 text-status-healthy",
  warn: "bg-status-degrade/15 text-status-degrade",
  bad: "bg-status-critical/15 text-status-critical",
};

export const PHASE_LABEL: Record<LifecyclePhase, string> = {
  stable: "Stable",
  quarantine: "Quarantine",
  deciding: "Deciding",
};

export const PHASE_TONE: Record<LifecyclePhase, Tone> = {
  stable: "good",
  quarantine: "info",
  deciding: "warn",
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  incident: "Incident",
  concept_drift: "Concept drift",
  model_decay: "Model decay",
  no_change: "No change",
  ambiguous: "Ambiguous",
  operator: "Operator",
  unattributed: "Unattributed",
  scheduled: "Scheduled",
};

export const ACTION_LABEL: Record<LifecycleAction, string> = {
  hold: "Hold",
  promote: "Promote",
  rollback: "Roll back",
  resume: "Resume",
  ask: "Ask operator",
};

export const ACTION_TONE: Record<LifecycleAction, Tone> = {
  promote: "good",
  rollback: "warn",
  hold: "bad",
  resume: "neutral",
  ask: "info",
};

export const TRIGGER_LABEL: Record<string, string> = {
  drift_up: "drift (score rising)",
  drift_down: "drift (score falling)",
  change_event: "deployment",
  scheduled: "scheduled check",
  operator: "operator check",
  operator_timeout: "query expired",
  operator_answer: "operator answer",
  manual: "operator",
};

export function pct(value: unknown, digits = 1): string {
  return typeof value === "number" ? `${(value * 100).toFixed(digits)}%` : "n/a";
}

/** The evidence behind an operator query, in the words the presenter would use. */
export function explainQuery(q: OperatorQuery): string[] {
  const e = q.evidence;
  return [
    `The serving model now alarms on ${pct(e.champion_tail_alarm_rate)} of recent events (stale above ${pct(e.stale_line)}).`,
    `A challenger retrained on the new behaviour alarms on only ${pct(e.challenger_tail_alarm_rate)}, so the shift is learnable.`,
    "No deployment or config change explains it, and without labels a new normal cannot be told apart from a long incident.",
  ];
}
