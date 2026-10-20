import type { ApiRuleCondition, ApiRuleThen } from "@/lib/api";

/**
 * Renders a rule's condition tree and action as a read-only greyed block.
 * Used by Level 2 (Customize) wherever `when`/`then` must not be edited.
 */
export function ConditionReadOnly({
  when,
  then,
  depth = 0,
}: {
  when: ApiRuleCondition;
  then: ApiRuleThen;
  depth?: number;
}) {
  return (
    <div className="space-y-1.5 font-mono text-[11px] text-muted-foreground">
      <ConditionNode node={when} depth={depth} />
      <div className="mt-2 flex flex-wrap gap-2">
        <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-blue-600">
          {then.action}
        </span>
        <span className="text-[11px] text-muted-foreground">
          conf {then.base_confidence} · risk {then.base_risk}
        </span>
      </div>
      {Object.keys(then.params).length > 0 && (
        <div className="mt-1 space-y-0.5 text-[10px]">
          {Object.entries(then.params).map(([k, v]) => (
            <p key={k}>
              {k}: <span className="text-foreground/80">{String(v)}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function ConditionNode({
  node,
  depth,
}: {
  node: ApiRuleCondition;
  depth: number;
}) {
  const pad = { paddingLeft: `${depth * 12}px` };
  const obj = node as unknown as Record<string, unknown>;

  if (obj && typeof obj === "object") {
    if ("all" in obj || "any" in obj) {
      const key = "all" in obj ? "all" : "any";
      const children = obj[key] as ApiRuleCondition[];
      return (
        <div style={pad}>
          <span className="text-foreground/70">{key === "all" ? "AND" : "OR"}</span>{" "}
          <span className="text-muted-foreground/70">({children.length})</span>
          <div className="mt-1 space-y-1">
            {children.map((c, i) => (
              <ConditionNode key={i} node={c} depth={depth + 1} />
            ))}
          </div>
        </div>
      );
    }
    if ("metric" in obj) {
      const v = Array.isArray(obj.value)
        ? `[${obj.value.join(", ")}]`
        : String(obj.value);
      return (
        <div style={pad}>
          <span className="text-foreground/80">{String(obj.metric)}</span>{" "}
          <span className="text-amber-600">{String(obj.op)}</span>{" "}
          <span>{v}</span>
        </div>
      );
    }
  }
  return <div style={pad}>{JSON.stringify(node)}</div>;
}
