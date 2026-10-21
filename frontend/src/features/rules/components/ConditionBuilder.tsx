import { Plus, Trash2, ChevronDown, Brackets } from "lucide-react";
import type { ApiRuleCondition, ApiRuleConditionLeaf } from "@/lib/api";
import { CONDITION_OPS, METRIC_SUGGESTIONS } from "../types";

type Leaf = { metric: string; op: string; value: unknown };
type Group = { all?: ApiRuleCondition[]; any?: ApiRuleCondition[] };

const inputCls =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

function isLeaf(node: ApiRuleCondition): node is ApiRuleConditionLeaf {
  return typeof node === "object" && node !== null && "metric" in node;
}

/** The builder's local shapes intentionally widen `op` to `string`; the API
 *  type narrows it to a literal union. These two helpers keep the conversions
 *  honest instead of scattering `as` casts through the tree. */
function groupOf(key: "all" | "any", children: ApiRuleCondition[]): ApiRuleCondition {
  return { [key]: children } as unknown as ApiRuleCondition;
}
function leafOf(l: Leaf): ApiRuleCondition {
  return l as unknown as ApiRuleCondition;
}

function valueToString(v: unknown): string {
  if (Array.isArray(v)) return v.join(", ");
  if (v === null || v === undefined) return "";
  return String(v);
}

/** Parse a "value" text box into a scalar, number, bool, or list. */
function parseValue(raw: string): unknown {
  const s = raw.trim();
  if (s === "") return "";
  if (s.includes(",")) {
    return s.split(",").map((p) => parseScalar(p.trim()));
  }
  if (s.startsWith("[") && s.endsWith("]")) {
    try {
      return JSON.parse(s.replace(/'/g, '"'));
    } catch {
      /* fall through */
    }
  }
  return parseScalar(s);
}

function parseScalar(s: string): unknown {
  if (s === "true") return true;
  if (s === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(s)) return Number(s);
  return s;
}

interface Props {
  value: ApiRuleCondition;
  onChange: (next: ApiRuleCondition) => void;
  /** When true, the root is rendered without a delete button (Level 2 read-only
   *  also uses this component but with `readOnly`). */
  readOnly?: boolean;
}

export function ConditionBuilder({ value, onChange, readOnly }: Props) {
  return (
    <div className="space-y-2">
      <NodeEditor
        node={value}
        onChange={onChange}
        onRemove={undefined}
        readOnly={readOnly}
      />
    </div>
  );
}

function NodeEditor({
  node,
  onChange,
  onRemove,
  readOnly,
}: {
  node: ApiRuleCondition;
  onChange: (next: ApiRuleCondition) => void;
  onRemove?: () => void;
  readOnly?: boolean;
}) {
  if (isLeaf(node)) {
    return (
      <LeafEditor
        leaf={node as Leaf}
        onChange={(l) => onChange(leafOf(l))}
        onRemove={onRemove}
        readOnly={readOnly}
      />
    );
  }

  const group = node as Group;
  const key: "all" | "any" = "all" in group ? "all" : "any";
  const children = (group[key] as ApiRuleCondition[]) ?? [];

  const setKey = (nextKey: "all" | "any") => onChange(groupOf(nextKey, children));

  const updateChild = (i: number, next: ApiRuleCondition) => {
    const copy = [...children];
    copy[i] = next;
    onChange(groupOf(key, copy));
  };

  const removeChild = (i: number) => {
    const copy = children.filter((_, idx) => idx !== i);
    onChange(groupOf(key, copy.length ? copy : [{ metric: "", op: ">=", value: "" } as unknown as ApiRuleCondition]));
  };

  const addChild = (kind: "leaf" | "group") => {
    const next =
      kind === "leaf"
        ? ({ metric: "anomaly.score", op: ">=", value: 0.6 } as unknown as ApiRuleCondition)
        : groupOf("all", [{ metric: "anomaly.score", op: ">=", value: 0.6 } as unknown as ApiRuleCondition]);
    onChange(groupOf(key, [...children, next]));
  };

  return (
    <div className="rounded-lg border border-border/60 bg-muted/20 p-3">
      <div className="mb-2 flex items-center gap-2">
        <Brackets className="size-3.5 text-muted-foreground" />
        <select
          value={key}
          disabled={readOnly}
          onChange={(e) => setKey(e.target.value as "all" | "any")}
          className={`${inputCls} w-32`}
        >
          <option value="all">ALL (AND)</option>
          <option value="any">ANY (OR)</option>
        </select>
        {children.length > 1 && (
          <span className="text-[10px] text-muted-foreground">
            every child must match
          </span>
        )}
        {onRemove && !readOnly && (
          <button
            type="button"
            onClick={onRemove}
            className="ml-auto rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-destructive"
            aria-label="Remove group"
          >
            <Trash2 className="size-3.5" />
          </button>
        )}
      </div>

      <div className="space-y-2 pl-2">
        {children.map((c, i) => (
          <NodeEditor
            key={i}
            node={c}
            onChange={(next) => updateChild(i, next)}
            onRemove={() => removeChild(i)}
            readOnly={readOnly}
          />
        ))}
      </div>

      {!readOnly && (
        <div className="mt-2 flex gap-2 pl-2">
          <button
            type="button"
            onClick={() => addChild("leaf")}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent"
          >
            <Plus className="size-3" /> Condition
          </button>
          <button
            type="button"
            onClick={() => addChild("group")}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent"
          >
            <Plus className="size-3" /> Group
          </button>
        </div>
      )}
    </div>
  );
}

function LeafEditor({
  leaf,
  onChange,
  onRemove,
  readOnly,
}: {
  leaf: Leaf;
  onChange: (next: Leaf) => void;
  onRemove?: () => void;
  readOnly?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/60 bg-background/40 p-2">
      <input
        list="metric-suggestions"
        value={leaf.metric}
        disabled={readOnly}
        placeholder="metric.path"
        onChange={(e) => onChange({ ...leaf, metric: e.target.value })}
        className={`${inputCls} min-w-[180px] flex-1 font-mono`}
      />
      <select
        value={leaf.op}
        disabled={readOnly}
        onChange={(e) => onChange({ ...leaf, op: e.target.value })}
        className={`${inputCls} w-24 font-mono`}
      >
        {CONDITION_OPS.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>
      <input
        value={valueToString(leaf.value)}
        disabled={readOnly}
        placeholder="value"
        onChange={(e) => onChange({ ...leaf, value: parseValue(e.target.value) })}
        className={`${inputCls} w-40 font-mono`}
      />
      {onRemove && !readOnly && (
        <button
          type="button"
          onClick={onRemove}
          className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-destructive"
          aria-label="Remove condition"
        >
          <Trash2 className="size-3.5" />
        </button>
      )}
    </div>
  );
}

/** Shared datalist — rendered once wherever ConditionBuilder is used. */
export function MetricSuggestions() {
  return (
    <datalist id="metric-suggestions">
      {METRIC_SUGGESTIONS.map((m) => (
        <option key={m} value={m} />
      ))}
    </datalist>
  );
}

export { ChevronDown };
