import type { ApiRuleGuardrails } from "@/lib/api";

const inputCls =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

interface Props {
  guardrails: ApiRuleGuardrails;
  onChange: (next: ApiRuleGuardrails) => void;
  readOnly?: boolean;
}

export function GuardrailsEditor({ guardrails, onChange, readOnly }: Props) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <label className="block">
        <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Cooldown (seconds)
        </span>
        <input
          type="number"
          min="0"
          value={guardrails.cooldown_seconds}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...guardrails, cooldown_seconds: Number(e.target.value) })
          }
          className={inputCls}
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Max per hour
        </span>
        <input
          type="number"
          min="1"
          value={guardrails.max_per_hour}
          disabled={readOnly}
          onChange={(e) =>
            onChange({ ...guardrails, max_per_hour: Number(e.target.value) })
          }
          className={inputCls}
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          Idempotency key
        </span>
        <input
          value={guardrails.idempotency_key ?? ""}
          disabled={readOnly}
          placeholder="optional"
          onChange={(e) =>
            onChange({ ...guardrails, idempotency_key: e.target.value || null })
          }
          className={`${inputCls} font-mono`}
        />
      </label>
    </div>
  );
}
