import { useRuleAudit } from "../data/useRuleAudit";
import { History, Plus, Pencil, Trash2, Power, RefreshCw } from "lucide-react";

const ACTION_META: Record<
  string,
  { icon: typeof Plus; className: string; label: string }
> = {
  CREATE: { icon: Plus, className: "text-green-600", label: "Created" },
  UPDATE: { icon: Pencil, className: "text-blue-600", label: "Updated" },
  DELETE: { icon: Trash2, className: "text-red-600", label: "Deleted" },
  TOGGLE: { icon: Power, className: "text-amber-600", label: "Toggled" },
  RELOAD: { icon: RefreshCw, className: "text-muted-foreground", label: "Reloaded" },
};

export function AuditLog({ ruleId }: { ruleId: string }) {
  const { entries, loading, error } = useRuleAudit(ruleId);

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading history…</p>;
  }
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No changes recorded for this rule yet.
      </p>
    );
  }

  return (
    <ol className="relative space-y-4 border-l border-border/60 pl-5">
      {entries.map((e) => {
        const meta = ACTION_META[e.action] ?? ACTION_META.RELOAD;
        const Icon = meta.icon;
        return (
          <li key={e.id} className="relative">
            <span className="absolute top-0.5 -left-[26px] flex size-4 items-center justify-center rounded-full border border-border bg-background">
              <Icon className={`size-2.5 ${meta.className}`} />
            </span>
            <div className="flex flex-wrap items-baseline gap-2">
              <span className={`text-xs font-medium ${meta.className}`}>
                {meta.label}
              </span>
              <span className="font-mono text-[10px] text-muted-foreground">
                {e.actor}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {new Date(e.created_at).toLocaleString()}
              </span>
            </div>
            {e.diff && <DiffView action={e.action} diff={e.diff} />}
          </li>
        );
      })}
    </ol>
  );
}

function DiffView({
  action,
  diff,
}: {
  action: string;
  diff: Record<string, unknown>;
}) {
  if (action === "TOGGLE") {
    const before = (diff.before as Record<string, unknown>) ?? {};
    const after = (diff.after as Record<string, unknown>) ?? {};
    return (
      <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
        enabled: {String(before.enabled)} → {String(after.enabled)}
      </p>
    );
  }

  const before = (diff.before as Record<string, unknown>) ?? {};
  const after = (diff.after as Record<string, unknown>) ?? {};
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  if (keys.size === 0) return null;

  return (
    <div className="mt-1 space-y-0.5">
      {[...keys].slice(0, 8).map((k) => (
        <p key={k} className="font-mono text-[10px] text-muted-foreground">
          <span className="text-foreground/70">{k}</span>:{" "}
          {shorten(before[k])} → <span className="text-foreground/90">{shorten(after[k])}</span>
        </p>
      ))}
    </div>
  );
}

function shorten(v: unknown): string {
  if (v === undefined) return "—";
  if (v === null) return "null";
  const s = typeof v === "object" ? JSON.stringify(v) : String(v);
  return s.length > 60 ? s.slice(0, 57) + "…" : s;
}

export { History };
