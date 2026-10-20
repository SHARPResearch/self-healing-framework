import { Plus, Trash2 } from "lucide-react";
import type { ApiRuleThen } from "@/lib/api";
import { ACTION_TYPES, RISK_LEVELS } from "../types";

const inputCls =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

interface Props {
  then: ApiRuleThen;
  onChange: (next: ApiRuleThen) => void;
  readOnly?: boolean;
}

export function ActionEditor({ then, onChange, readOnly }: Props) {
  const setParam = (key: string, value: string) => {
    onChange({ ...then, params: { ...then.params, [key]: value } });
  };
  const removeParam = (key: string) => {
    const next = { ...then.params };
    delete next[key];
    onChange({ ...then, params: next });
  };
  const addParam = () => {
    let i = 1;
    let key = "param";
    while (key in then.params) key = `param${++i}`;
    onChange({ ...then, params: { ...then.params, [key]: "" } });
  };

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Action">
          <select
            value={then.action}
            disabled={readOnly}
            onChange={(e) => onChange({ ...then, action: e.target.value })}
            className={`${inputCls} font-mono`}
          >
            {ACTION_TYPES.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Base confidence">
          <input
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={then.base_confidence}
            disabled={readOnly}
            onChange={(e) =>
              onChange({ ...then, base_confidence: Number(e.target.value) })
            }
            className={inputCls}
          />
        </Field>
        <Field label="Base risk">
          <select
            value={then.base_risk}
            disabled={readOnly}
            onChange={(e) =>
              onChange({ ...then, base_risk: e.target.value as ApiRuleThen["base_risk"] })
            }
            className={inputCls}
          >
            {RISK_LEVELS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Action parameters
          </span>
          {!readOnly && (
            <button
              type="button"
              onClick={addParam}
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <Plus className="size-3" /> Add
            </button>
          )}
        </div>
        <div className="space-y-2">
          {Object.entries(then.params).length === 0 && (
            <p className="text-[11px] text-muted-foreground">No parameters.</p>
          )}
          {Object.entries(then.params).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2">
              <input
                value={k}
                disabled={readOnly}
                onChange={(e) => {
                  const next = { ...then.params };
                  delete next[k];
                  next[e.target.value] = v;
                  onChange({ ...then, params: next });
                }}
                className={`${inputCls} w-40 font-mono`}
              />
              <input
                value={String(v ?? "")}
                disabled={readOnly}
                placeholder="{{ service.id }}"
                onChange={(e) => setParam(k, e.target.value)}
                className={`${inputCls} flex-1 font-mono`}
              />
              {!readOnly && (
                <button
                  type="button"
                  onClick={() => removeParam(k)}
                  className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-destructive"
                  aria-label="Remove parameter"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>
        {!readOnly && (
          <p className="mt-1.5 text-[10px] text-muted-foreground">
            Params support templates:{" "}
            <code className="font-mono">{"{{ service.id }}"}</code>,{" "}
            <code className="font-mono">{"{{ service.namespace }}"}</code>,{" "}
            <code className="font-mono">{"{{ anomaly.id }}"}</code>
          </p>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}
