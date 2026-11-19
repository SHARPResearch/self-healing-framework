// frontend\src\features\decisions\lib\steps.ts
//
// The decision's reasoning as an ordered list of steps, derived from the
// decision_log row alone. Shared by the "Steps" tab and by the run graph's
// inspector, so the two views can never disagree about a value.
import type { ApiDecision } from "@/lib/api";
import { BadgeCheck, Gauge, Search, Target, Waves } from "lucide-react";
import type { FlowStep, FlowStepDetail } from "../types";

function num(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function severityTone(label: string): "good" | "warn" | "bad" | "accent" {
  if (label === "CRITICAL") return "bad";
  if (label === "HIGH") return "warn";
  if (label === "MEDIUM") return "accent";
  return "good";
}

function policyTone(
  outcome: string | null,
): "good" | "warn" | "bad" | "accent" | "default" {
  if (outcome === "AUTO_EXECUTE") return "good";
  if (outcome === "SHADOW_MODE") return "accent";
  if (outcome === "HUMAN_LOOP") return "warn";
  if (outcome === "BLOCK") return "bad";
  if (outcome === "NO_RULE_MATCHED") return "bad";
  return "default";
}

export function buildSteps(d: ApiDecision): FlowStep[] {
  const ctx = d.context;
  const sev = d.severity;
  const sel = d.selection;
  const upstream = ctx?.upstream ?? [];
  const downstream = ctx?.downstream ?? [];
  const blastMembers = ctx?.blast_members ?? [];
  const rejected = sel?.rejected ?? [];

  const step1: FlowStep = {
    id: "context",
    title: "Context assembly",
    icon: Search,
    status: "done",
    summary: `Loaded ${upstream.length} upstream, ${downstream.length} downstream dependencies`,
    details: [
      { label: "Service", value: d.service_id, mono: true },
      {
        label: "Health",
        value: (ctx?.service_health ?? "unknown").toUpperCase(),
        tone:
          ctx?.service_health === "down"
            ? "bad"
            : ctx?.service_health === "degraded"
              ? "warn"
              : "good",
      },
      { label: "Upstream", value: upstream.join(", ") || "—", mono: true },
      { label: "Downstream", value: downstream.join(", ") || "—", mono: true },
      { label: "Centrality", value: num(d.centrality, 1).toFixed(3), mono: true },
      {
        label: "Blast factor",
        value: num(d.blast_factor, 1).toFixed(3),
        mono: true,
        tone: num(d.blast_factor, 1) >= 1.35 ? "warn" : "default",
      },
    ],
  };

  const kind = ctx?.anomaly_kind ?? "UNKNOWN";
  const step2: FlowStep = {
    id: "cascade",
    title: "Cascade analysis",
    icon: Waves,
    status: "done",
    summary: `Classified as ${kind}`,
    details: [
      {
        label: "Kind",
        value: kind,
        tone:
          kind === "CASCADING"
            ? "warn"
            : kind === "UPSTREAM"
              ? "accent"
              : "good",
      },
      {
        label: "Blast radius size",
        value: `${blastMembers.length} services`,
        mono: true,
      },
      {
        label: "Affected services",
        value: blastMembers.join(", ") || "none",
        mono: true,
      },
    ],
  };

  const step3: FlowStep = {
    id: "severity",
    title: "Severity calculation",
    icon: Gauge,
    status: "done",
    summary: `base ${num(sev?.base_severity).toFixed(2)} × centrality ${num(sev?.centrality).toFixed(2)} × blast ${num(sev?.blast_factor).toFixed(2)} = ${num(sev?.effective_severity).toFixed(3)} (${sev?.label ?? "—"})`,
    details: [
      { label: "Base severity", value: num(sev?.base_severity).toFixed(2), mono: true },
      { label: "Centrality weight", value: num(sev?.centrality).toFixed(3), mono: true },
      {
        label: "Blast radius factor",
        value: num(sev?.blast_factor).toFixed(3),
        mono: true,
      },
      {
        label: "Effective severity",
        value: num(sev?.effective_severity).toFixed(3),
        mono: true,
        tone: "accent",
      },
      {
        label: "Normalized",
        value: `${(num(sev?.normalized) * 100).toFixed(1)}%`,
        mono: true,
      },
      { label: "Label", value: sev?.label ?? "—", tone: severityTone(sev?.label ?? "") },
    ],
  };

  const step4: FlowStep = {
    id: "rules",
    title: "Rule matching",
    icon: Target,
    status: "done",
    summary: d.rule_id
      ? `Matched ${d.rule_id} (1 candidate, ${rejected.length} rejected)`
      : `No rule matched`,
    details: [
      {
        label: "Selected rule",
        value: d.rule_id ?? "—",
        mono: true,
        tone: d.rule_id ? "good" : "bad",
      },
      { label: "Rule version", value: d.rule_version?.toString() ?? "—", mono: true },
      { label: "Strategy", value: sel?.strategy ?? "—", mono: true },
      { label: "Reason", value: sel?.reason || "—", mono: false },
      ...(rejected.length > 0
        ? [
            {
              label: "Rejected",
              value: rejected.map((r) => String(r?.rule_id ?? "?")).join(", "),
              mono: true,
              tone: "warn" as const,
            },
          ]
        : []),
    ],
  };

  const step5: FlowStep = {
    id: "decision",
    title: "Final decision",
    icon: BadgeCheck,
    status: "done",
    summary: `${d.action} with ${(num(d.confidence?.final) * 100).toFixed(1)}% confidence`,
    details: [
      { label: "Action", value: d.action, mono: true, tone: "accent" },
      {
        label: "Detection conf",
        value: `${(num(d.confidence?.detection) * 100).toFixed(1)}%`,
        mono: true,
      },
      {
        label: "Rule conf",
        value: `${(num(d.confidence?.rule) * 100).toFixed(1)}%`,
        mono: true,
      },
      {
        label: "Final conf",
        value: `${(num(d.confidence?.final) * 100).toFixed(1)}%`,
        mono: true,
        tone: "accent",
      },
      {
        label: "Risk",
        value: d.base_risk,
        tone:
          d.base_risk === "HIGH"
            ? "bad"
            : d.base_risk === "MEDIUM"
              ? "warn"
              : "good",
      },
      {
        label: "Policy outcome",
        value: d.policy?.outcome ?? "PENDING",
        tone: policyTone(d.policy?.outcome ?? null),
      },
    ],
  };

  return [step1, step2, step3, step4, step5];
}

/** Just the key/value rows for one step id, for the graph's inspector. */
export function detailsFor(stepId: string, d: ApiDecision): FlowStepDetail[] {
  return buildSteps(d).find((s) => s.id === stepId)?.details ?? [];
}
