import type { ApiRule } from "@/lib/api";

/**
 * YAML-ish preview of a rule. Deliberately hand-rendered instead of pulling
 * the `yaml` package — the shapes here are small and fixed, and a plain
 * <pre> keeps the bundle clean (see frontend/CLAUDE.md's dependency discipline).
 */
export function RulePreview({ rule }: { rule: Partial<ApiRule> }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-lg border border-border/60 bg-muted/30 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
      {toYaml(rule)}
    </pre>
  );
}

function toYaml(rule: Partial<ApiRule>): string {
  const lines: string[] = [];
  lines.push(`id: ${rule.id ?? ""}`);
  if (rule.priority !== undefined) lines.push(`priority: ${rule.priority}`);
  if (rule.description) lines.push(`description: ${quote(rule.description)}`);
  if (rule.enabled !== undefined) lines.push(`enabled: ${rule.enabled}`);
  if (rule.status) lines.push(`status: ${rule.status}`);

  if (rule.applies_to) {
    lines.push("applies_to:");
    lines.push(`  layers: ${inlineList(rule.applies_to.layers)}`);
    lines.push(`  services: ${inlineList(rule.applies_to.services)}`);
    if (rule.applies_to.exclude_services?.length)
      lines.push(`  exclude_services: ${inlineList(rule.applies_to.exclude_services)}`);
  }

  lines.push("when:");
  lines.push(condYaml(rule.when, 1));

  lines.push("then:");
  lines.push(`  action: ${rule.then?.action ?? ""}`);
  if (rule.then?.params && Object.keys(rule.then.params).length) {
    lines.push("  params:");
    for (const [k, v] of Object.entries(rule.then.params)) {
      lines.push(`    ${k}: ${quote(String(v))}`);
    }
  }
  if (rule.then) {
    lines.push(`  base_confidence: ${rule.then.base_confidence}`);
    lines.push(`  base_risk: ${rule.then.base_risk}`);
  }

  if (rule.guardrails) {
    lines.push("guardrails:");
    lines.push(`  cooldown_seconds: ${rule.guardrails.cooldown_seconds}`);
    lines.push(`  max_per_hour: ${rule.guardrails.max_per_hour}`);
    lines.push(`  idempotency_key: ${rule.guardrails.idempotency_key ?? "null"}`);
  }

  if (rule.tags?.length) lines.push(`tags: ${inlineList(rule.tags)}`);
  return lines.join("\n");
}

function condYaml(node: unknown, depth: number): string {
  const pad = "  ".repeat(depth);
  const obj = node as Record<string, unknown> | null;
  if (!obj || typeof obj !== "object") return `${pad}{}`;

  if ("all" in obj || "any" in obj) {
    const key = "all" in obj ? "all" : "any";
    const items = (obj[key] as unknown[]) ?? [];
    const rendered = items
      .map((c) => {
        const inner = condYaml(c, depth + 1).trimStart();
        return `${pad}  - ${inner.trim()}`;
      })
      .join("\n");
    return `${pad}${key}:\n${rendered}`;
  }

  if ("metric" in obj) {
    return [
      `${pad}- metric: ${obj.metric}`,
      `${pad}  op: ${obj.op}`,
      `${pad}  value: ${quote(String(obj.value))}`,
    ].join("\n");
  }
  return `${pad}{}`;
}

function inlineList(list: string[]): string {
  if (!list?.length) return "[]";
  return `[${list.map((s) => (s === "*" ? '"*"' : s)).join(", ")}]`;
}

function quote(s: string): string {
  if (s === null || s === undefined) return "null";
  if (/^-?\d+(\.\d+)?$/.test(s) || s === "true" || s === "false") return s;
  if (s.startsWith("[") || s.startsWith("{")) return s;
  return `"${s.replace(/"/g, '\\"')}"`;
}
