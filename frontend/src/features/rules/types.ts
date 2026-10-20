import type { ApiRule, RuleStatus } from "@/lib/api";

export type {
  ApiRule,
  ApiRuleCondition,
  ApiRuleConditionLeaf,
  ApiRuleConditionAll,
  ApiRuleConditionAny,
  ApiRuleThen,
  ApiRuleGuardrails,
  ApiRuleAppliesTo,
  ApiRuleAuditEntry,
  ApiRuleValidateResult,
  RuleListFilter,
  RuleStatus,
} from "@/lib/api";

export type RuleTab = "all" | "default" | "custom" | "templates" | "archived";

export const RULE_TABS: { value: RuleTab; label: string }[] = [
  { value: "all", label: "All" },
  { value: "default", label: "Default" },
  { value: "custom", label: "Custom" },
  { value: "templates", label: "Templates" },
  { value: "archived", label: "Archived" },
];

export const KNOWN_LAYERS = ["edge", "bff", "domain", "data"] as const;

export const ACTION_TYPES = [
  "RESTART_POD",
  "SCALE_UP",
  "SCALE_DOWN",
  "ROLLBACK",
  "OPEN_CIRCUIT",
  "CLOSE_CIRCUIT",
  "FLUSH_CACHE",
  "INCREASE_DB_POOL",
  "SCALE_CONSUMERS",
  "DRAIN_NODE",
  "NOOP",
] as const;

export const CONDITION_OPS = [
  ">",
  ">=",
  "<",
  "<=",
  "==",
  "!=",
  "in",
  "not_in",
  "contains",
] as const;

export const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH"] as const;

/** Common metric paths the context resolver understands — offered as suggestions. */
export const METRIC_SUGGESTIONS = [
  "anomaly.score",
  "anomaly.severity",
  "anomaly.deviation_sigma",
  "service.health",
  "service.layer",
  "service.criticality",
  "infra.cpu.usage_pct",
  "infra.memory.pct",
  "infra.restarts_last_5m",
  "infra.disk.write_iops",
  "infra.uptime_seconds",
  "app.error_rate",
  "app.saturation_pct",
  "app.latency_ms.p95",
  "app.queue_depth",
  "graph.neighbor_anomaly_count",
  "blast_radius.size",
  "blast_radius.factor",
  "centrality",
  "classification.kind",
];

/** Which level of control applies to a rule. */
export function ruleKind(rule: ApiRule): "template" | "default" | "custom" {
  if (rule.is_template) return "template";
  if (rule.is_default) return "default";
  return "custom";
}

export function statusColor(status: RuleStatus): string {
  switch (status) {
    case "ACTIVE":
      return "border-green-500/30 bg-green-500/15 text-green-600";
    case "DRAFT":
      return "border-yellow-500/30 bg-yellow-500/15 text-yellow-600";
    case "ARCHIVED":
      return "border-border bg-muted/40 text-muted-foreground";
  }
}

/** Slugify a description into a rule id. */
export function slugify(input: string): string {
  return input
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}
