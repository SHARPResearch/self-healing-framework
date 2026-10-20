import { useNavigate } from "react-router-dom";
import { Pencil, Copy, Trash2, ShieldAlert } from "lucide-react";
import type { ApiRule } from "@/lib/api";
import { EnableToggle } from "./EnableToggle";
import { RuleTypeBadge } from "./RuleTypeBadge";
import { StatusBadge } from "./StatusBadge";

interface Props {
  rules: ApiRule[];
  loading: boolean;
  error: string | null;
  onToggle: (rule: ApiRule, next: boolean) => void;
  onEdit: (rule: ApiRule) => void;
  onClone: (rule: ApiRule) => void;
  onDelete: (rule: ApiRule) => void;
  busyId: string | null;
}

export function RuleTable({
  rules,
  loading,
  error,
  onToggle,
  onEdit,
  onClone,
  onDelete,
  busyId,
}: Props) {
  const navigate = useNavigate();
  const colCount = 9;

  return (
    <div className="overflow-hidden rounded-xl border border-border/60">
      <table className="w-full text-sm">
        <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">On</th>
            <th className="px-3 py-2 text-left">Rule ID</th>
            <th className="px-3 py-2 text-right">Priority</th>
            <th className="px-3 py-2 text-left">Layer</th>
            <th className="px-3 py-2 text-left">Action</th>
            <th className="px-3 py-2 text-left">Status</th>
            <th className="px-3 py-2 text-left">Type</th>
            <th className="px-3 py-2 text-left">Updated</th>
            <th className="px-3 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-muted-foreground">
                Loading rules…
              </td>
            </tr>
          )}
          {error && (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-destructive">
                {error}
              </td>
            </tr>
          )}
          {!loading && !error && rules.length === 0 && (
            <tr>
              <td colSpan={colCount} className="px-3 py-8 text-center text-muted-foreground">
                No rules in this view.
              </td>
            </tr>
          )}
          {rules.map((r) => (
            <tr
              key={r.id}
              className={`border-t border-border/60 transition-colors hover:bg-accent/50 ${
                busyId === r.id ? "opacity-60" : ""
              }`}
            >
              <td className="px-3 py-2">
                <EnableToggle
                  enabled={r.enabled}
                  disabled={busyId === r.id}
                  onToggle={(next) => onToggle(r, next)}
                />
              </td>
              <td className="px-3 py-2">
                <button
                  onClick={() => navigate(`/rules/${encodeURIComponent(r.id)}`)}
                  className="text-left"
                >
                  <div className="font-mono text-xs font-medium hover:underline">
                    {r.id}
                  </div>
                  <div className="max-w-[280px] truncate text-[10px] text-muted-foreground">
                    {r.description}
                  </div>
                </button>
              </td>
              <td className="px-3 py-2 text-right">
                <span className="rounded-md border border-border/60 bg-muted/40 px-2 py-0.5 font-mono text-xs">
                  {r.priority}
                </span>
              </td>
              <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                {r.applies_to.layers.length
                  ? r.applies_to.layers.join(", ")
                  : "any"}
              </td>
              <td className="px-3 py-2">
                <span className="rounded-full bg-blue-500/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider text-blue-600">
                  {r.then.action}
                </span>
              </td>
              <td className="px-3 py-2">
                <StatusBadge status={r.status} />
              </td>
              <td className="px-3 py-2">
                <RuleTypeBadge rule={r} />
              </td>
              <td className="px-3 py-2 font-mono text-[10px] text-muted-foreground">
                {r.updated_at ? new Date(r.updated_at).toLocaleString() : "—"}
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center justify-end gap-1">
                  <IconAction
                    title={r.is_template ? "Create from template" : "Edit"}
                    onClick={() => (r.is_template ? onClone(r) : onEdit(r))}
                  >
                    <Pencil className="size-3.5" />
                  </IconAction>
                  <IconAction title="Clone as custom rule" onClick={() => onClone(r)}>
                    <Copy className="size-3.5" />
                  </IconAction>
                  {r.is_default || r.is_template ? (
                    <span
                      title="Default & template rules cannot be deleted"
                      className="cursor-not-allowed rounded-md p-1.5 text-muted-foreground/40"
                    >
                      <ShieldAlert className="size-3.5" />
                    </span>
                  ) : (
                    <IconAction
                      title="Delete"
                      danger
                      onClick={() => onDelete(r)}
                    >
                      <Trash2 className="size-3.5" />
                    </IconAction>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function IconAction({
  title,
  onClick,
  danger,
  children,
}: {
  title: string;
  onClick: () => void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className={`rounded-md p-1.5 text-muted-foreground hover:bg-accent ${
        danger ? "hover:text-destructive" : "hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}
