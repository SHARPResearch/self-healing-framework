import { useNavigate } from "react-router-dom";
import { Pencil, Copy, Trash2, ShieldAlert } from "lucide-react";
import type { ApiRule } from "@/lib/api";
import { ListTable } from "@/shared/components/ListTable";
import type { ListColumn, SortState } from "@/shared/components/ListTable";
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
  sort: SortState | null;
  onSortChange: (sort: SortState) => void;
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
  sort,
  onSortChange,
}: Props) {
  const navigate = useNavigate();

  const columns: ListColumn<ApiRule>[] = [
    {
      key: "enabled",
      header: "On",
      render: (r) => (
        <EnableToggle
          enabled={r.enabled}
          disabled={busyId === r.id}
          onToggle={(next) => onToggle(r, next)}
        />
      ),
    },
    {
      key: "id",
      header: "Rule ID",
      sortValue: (r) => r.id,
      render: (r) => (
        <button
          onClick={() => navigate(`/rules/${encodeURIComponent(r.id)}`)}
          className="text-left"
        >
          <div className="font-mono text-xs font-medium hover:underline">{r.id}</div>
          <div className="max-w-[280px] truncate text-[10px] text-muted-foreground">
            {r.description}
          </div>
        </button>
      ),
    },
    {
      key: "priority",
      header: "Priority",
      sortValue: (r) => r.priority,
      className: "text-right",
      render: (r) => (
        <span className="rounded-md border border-border/60 bg-muted/40 px-2 py-0.5 font-mono text-xs">
          {r.priority}
        </span>
      ),
    },
    {
      key: "layer",
      header: "Layer",
      sortValue: (r) => r.applies_to.layers.join(", "),
      className: "font-mono text-xs text-muted-foreground",
      render: (r) => (r.applies_to.layers.length ? r.applies_to.layers.join(", ") : "any"),
    },
    {
      key: "action",
      header: "Action",
      sortValue: (r) => r.then.action,
      render: (r) => (
        <span className="rounded-full bg-blue-500/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider text-blue-600">
          {r.then.action}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortValue: (r) => r.status,
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: "type",
      header: "Type",
      sortValue: (r) => (r.is_template ? "template" : r.is_default ? "default" : "custom"),
      render: (r) => <RuleTypeBadge rule={r} />,
    },
    {
      key: "updated_at",
      header: "Updated",
      sortValue: (r) => r.updated_at ?? "",
      className: "font-mono text-[10px] text-muted-foreground",
      render: (r) => (r.updated_at ? new Date(r.updated_at).toLocaleString() : "—"),
    },
    {
      key: "actions",
      header: "Actions",
      className: "text-right",
      headerClassName: "text-right",
      render: (r) => (
        <div className={`flex items-center justify-end gap-1 ${busyId === r.id ? "opacity-60" : ""}`}>
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
            <IconAction title="Delete" danger onClick={() => onDelete(r)}>
              <Trash2 className="size-3.5" />
            </IconAction>
          )}
        </div>
      ),
    },
  ];

  return (
    <ListTable
      columns={columns}
      rows={rules}
      rowKey={(r) => r.id}
      loading={loading}
      error={error}
      emptyMessage="No rules in this view."
      sort={sort}
      onSortChange={onSortChange}
    />
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
