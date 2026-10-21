import type { ApiRule } from "@/lib/api";
import { ruleKind } from "../types";

const STYLES: Record<ReturnType<typeof ruleKind>, string> = {
  default: "border-blue-500/30 bg-blue-500/15 text-blue-600",
  custom: "border-purple-500/30 bg-purple-500/15 text-purple-600",
  template: "border-border bg-muted/40 text-muted-foreground",
};

const LABELS: Record<ReturnType<typeof ruleKind>, string> = {
  default: "Default",
  custom: "Custom",
  template: "Template",
};

export function RuleTypeBadge({
  rule,
  kindOverride,
}: {
  rule: Pick<ApiRule, "is_default" | "is_template">;
  kindOverride?: ReturnType<typeof ruleKind>;
}) {
  const kind = kindOverride ?? ruleKind(rule as ApiRule);
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider ${STYLES[kind]}`}
    >
      {LABELS[kind]}
    </span>
  );
}
