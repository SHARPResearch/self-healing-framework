import type { ApiDecision } from "@/lib/api";
import { BadgeCheck, Gauge, Search, Target, Waves } from "lucide-react";
import type { FlowStep } from "../types";
import { StepCard } from "./StepCard";

interface Props {
  decision: ApiDecision;
}

export function DecisionFlow({ decision }: Props) {
  const steps = buildSteps(decision);
  return (
    <div className="space-y-0">
      {steps.map((s, i) => (
        <StepCard key={s.id} step={s} isLast={i === steps.length - 1} />
      ))}
    </div>
  );
}

function buildSteps(d: ApiDecision): FlowStep[] {
  const ctx = d.context;
  const sev = d.severity;
  const sel = d.selection;

  // ── Step 1: Context assembly ────────────────────────────────
  const step1: FlowStep = {
    id: "context",
    title: "Context assembly",
    icon: Search,
    status: "done",
    summary: `Loaded ${ctx.upstream.length} upstream, ${ctx.downstream.length} downstream dependencies`,
    details: [
      { label: "Service", value: d.service_id, mono: true },
      {
        label: "Health",
        value: ctx.service_health.toUpperCase(),
        tone:
          ctx.service_health === "down"
            ? "bad"
            : ctx.service_health === "degraded"
              ? "warn"
              : "good",
      },
      { label: "Upstream", value: ctx.upstream.join(", ") || "—", mono: true },
      {
        label: "Downstream",
        value: ctx.downstream.join(", ") || "—",
        mono: true,
      },
      { label: "Centrality", value: d.centrality.toFixed(3), mono: true },
      {
        label: "Blast factor",
        value: d.blast_factor.toFixed(3),
        mono: true,
        tone: d.blast_factor >= 1.35 ? "warn" : "default",
      },
    ],
  };

  // ── Step 2: Cascade analysis ────────────────────────────────
  const kind = ctx.anomaly_kind;
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
        value: `${ctx.blast_members.length} services`,
        mono: true,
      },
      {
        label: "Affected services",
        value: ctx.blast_members.join(", ") || "none",
        mono: true,
      },
    ],
  };

  // ── Step 3: Severity ────────────────────────────────────────
  const step3: FlowStep = {
    id: "severity",
    title: "Severity calculation",
    icon: Gauge,
    status: "done",
    summary: `base ${sev.base_severity.toFixed(2)} × centrality ${sev.centrality.toFixed(2)} × blast ${sev.blast_factor.toFixed(2)} = ${sev.effective_severity.toFixed(3)} (${sev.label})`,
    details: [
      {
        label: "Base severity",
        value: sev.base_severity.toFixed(2),
        mono: true,
      },
      {
        label: "Centrality weight",
        value: sev.centrality.toFixed(3),
        mono: true,
      },
      {
        label: "Blast radius factor",
        value: sev.blast_factor.toFixed(3),
        mono: true,
      },
      {
        label: "Effective severity",
        value: sev.effective_severity.toFixed(3),
        mono: true,
        tone: "accent",
      },
      {
        label: "Normalized",
        value: `${(sev.normalized * 100).toFixed(1)}%`,
        mono: true,
      },
      { label: "Label", value: sev.label, tone: severityTone(sev.label) },
    ],
  };

  // ── Step 4: Rule matching ───────────────────────────────────
  const rejectedCount = sel.rejected?.length ?? 0;
  const step4: FlowStep = {
    id: "rules",
    title: "Rule matching",
    icon: Target,
    status: "done",
    summary: d.rule_id
      ? `Matched ${d.rule_id} (1 candidate, ${rejectedCount} rejected)`
      : `No rule matched`,
    details: [
      {
        label: "Selected rule",
        value: d.rule_id ?? "—",
        mono: true,
        tone: d.rule_id ? "good" : "bad",
      },
      {
        label: "Rule version",
        value: d.rule_version?.toString() ?? "—",
        mono: true,
      },
      { label: "Strategy", value: sel.strategy, mono: true },
      { label: "Reason", value: sel.reason, mono: false },
      ...(rejectedCount > 0
        ? [
            {
              label: "Rejected",
              value: sel.rejected.map((r: any) => r.rule_id).join(", "),
              mono: true,
              tone: "warn" as const,
            },
          ]
        : []),
    ],
  };

  // ── Step 5: Decision ────────────────────────────────────────
  const step5: FlowStep = {
    id: "decision",
    title: "Final decision",
    icon: BadgeCheck,
    status: "done",
    summary: `${d.action} with ${(d.confidence.final * 100).toFixed(1)}% confidence`,
    details: [
      { label: "Action", value: d.action, mono: true, tone: "accent" },
      {
        label: "Detection conf",
        value: `${(d.confidence.detection * 100).toFixed(1)}%`,
        mono: true,
      },
      {
        label: "Rule conf",
        value: `${(d.confidence.rule * 100).toFixed(1)}%`,
        mono: true,
      },
      {
        label: "Final conf",
        value: `${(d.confidence.final * 100).toFixed(1)}%`,
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
        value: d.policy.outcome ?? "PENDING",
        tone: policyTone(d.policy.outcome),
      },
    ],
  };

  return [step1, step2, step3, step4, step5];
}

function severityTone(label: string): "good" | "warn" | "bad" | "accent" {
  if (label === "CRITICAL") return "bad";
  if (label === "HIGH") return "warn";
  if (label === "MEDIUM") return "accent";
  return "good";
}

function policyTone(
  outcome: string | null,
): "good" | "warn" | "bad" | "accent" {
  if (outcome === "AUTO_EXECUTE") return "good";
  if (outcome === "SHADOW_MODE") return "accent";
  if (outcome === "HUMAN_LOOP") return "warn";
  if (outcome === "BLOCK") return "bad";
  if (outcome === "NO_RULE_MATCHED") return "bad";
  return "default" as any;
}
