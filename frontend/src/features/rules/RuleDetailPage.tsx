import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Copy, Power, Trash2, Pencil, LockKeyhole } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import {
  deleteRule,
  fetchRule,
  patchRule,
  toggleRule,
  type ApiRule,
} from "@/lib/api";
import { RulePreview } from "./components/RulePreview";
import { AuditLog } from "./components/AuditLog";
import { RuleTypeBadge } from "./components/RuleTypeBadge";
import { StatusBadge } from "./components/StatusBadge";
import { CustomizeModal } from "./components/CustomizeModal";
import { RuleBuilderModal } from "./components/RuleBuilderModal";
import { ToastHost } from "./components/ToastHost";
import { toast } from "./components/toast";
import { createCustomRule } from "@/lib/api";
import { ruleKind } from "./types";

type Tab = "definition" | "history";

export function RuleDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [rule, setRule] = useState<ApiRule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("definition");
  const [editing, setEditing] = useState<ApiRule | null>(null);
  const [cloneSeed, setCloneSeed] = useState<ApiRule | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetchRule(id);
      setRule(r);
      setError(null);
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleToggle = async () => {
    if (!rule) return;
    try {
      const res = await toggleRule(rule.id);
      toast(res.enabled ? "Rule enabled" : "Rule disabled", "success", rule.id);
      load();
    } catch (e) {
      toast("Toggle failed", "error", String((e as Error).message));
    }
  };

  const handleDelete = async () => {
    if (!rule) return;
    if (!window.confirm(`Delete custom rule "${rule.id}"?`)) return;
    try {
      await deleteRule(rule.id);
      toast("Rule deleted", "success", rule.id);
      navigate("/rules");
    } catch (e) {
      toast("Delete failed", "error", String((e as Error).message));
    }
  };

  const handlePatch = async (ruleId: string, patch: Record<string, unknown>) => {
    await patchRule(ruleId, patch as never);
    await load();
  };

  const handleCreate = async (
    payload: Record<string, unknown>,
    status: "DRAFT" | "ACTIVE",
  ) => {
    const res = await createCustomRule({ ...payload, status } as never);
    navigate(`/rules/${encodeURIComponent(res.rule.id)}`);
  };

  if (loading) {
    return (
      <AppShell pageTitle="Rule">
        <p className="text-sm text-muted-foreground">Loading rule…</p>
      </AppShell>
    );
  }

  if (error || !rule) {
    return (
      <AppShell pageTitle="Rule">
        <div className="space-y-3">
          <p className="text-sm text-destructive">{error ?? "Rule not found"}</p>
          <Button variant="outline" size="sm" onClick={() => navigate("/rules")}>
            <ArrowLeft className="size-3.5" /> Back to rules
          </Button>
        </div>
      </AppShell>
    );
  }

  const kind = ruleKind(rule);

  return (
    <AppShell pageTitle="Rule detail">
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => navigate("/rules")}
        >
          <ArrowLeft className="size-3.5" /> Rules
        </Button>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-mono text-lg font-semibold">{rule.id}</h2>
              <RuleTypeBadge rule={rule} />
              <StatusBadge status={rule.status} />
            </div>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              {rule.description || "No description."}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={handleToggle}>
              <Power className="size-3.5" />
              {rule.enabled ? "Disable" : "Enable"}
            </Button>
            {kind !== "template" && (
              <Button variant="outline" size="sm" onClick={() => setEditing(rule)}>
                <Pencil className="size-3.5" /> Edit
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setCloneSeed(rule)}>
              <Copy className="size-3.5" /> Clone
            </Button>
            {kind === "custom" ? (
              <Button variant="destructive" size="sm" onClick={handleDelete}>
                <Trash2 className="size-3.5" /> Delete
              </Button>
            ) : (
              <span
                title="Default & template rules cannot be deleted"
                className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground"
              >
                <LockKeyhole className="size-3.5" /> Protected
              </span>
            )}
          </div>
        </div>

        {/* Facts strip */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Fact label="Priority" value={String(rule.priority)} mono />
          <Fact label="Action" value={rule.then.action} mono />
          <Fact label="Layers" value={rule.applies_to.layers.join(", ") || "any"} />
          <Fact label="Enabled" value={rule.enabled ? "yes" : "no"} />
        </div>

        {/* Tabs */}
        <div className="flex gap-2">
          {(["definition", "history"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
                tab === t
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "definition" ? (
          <div className="space-y-4">
            <section>
              <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Definition
              </p>
              <RulePreview rule={rule} />
            </section>
            <section className="grid gap-3 sm:grid-cols-2">
              <Panel title="Metadata">
                <KV k="Created by" v={rule.created_by} />
                <KV k="Version" v={String(rule.version)} />
                <KV k="Parent rule" v={rule.parent_rule_id ?? "—"} />
                <KV k="Created" v={fmt(rule.created_at)} />
                <KV k="Updated" v={fmt(rule.updated_at)} />
              </Panel>
              <Panel title="Action parameters">
                {Object.keys(rule.then.params).length === 0 ? (
                  <p className="text-[11px] text-muted-foreground">None.</p>
                ) : (
                  Object.entries(rule.then.params).map(([k, v]) => (
                    <KV key={k} k={k} v={String(v)} mono />
                  ))
                )}
              </Panel>
            </section>
          </div>
        ) : (
          <AuditLog ruleId={rule.id} />
        )}
      </div>

      <CustomizeModal
        rule={editing}
        onClose={() => setEditing(null)}
        onSave={handlePatch}
        onClone={(r) => {
          setEditing(null);
          setCloneSeed(r);
        }}
      />

      <RuleBuilderModal
        open={!!cloneSeed}
        seed={cloneSeed}
        onClose={() => setCloneSeed(null)}
        onSave={handleCreate}
      />

      <ToastHost />
    </AppShell>
  );
}

function fmt(v: string | null): string {
  return v ? new Date(v).toLocaleString() : "—";
}

function Fact({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/40 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className={`mt-0.5 text-sm ${mono ? "font-mono" : ""}`}>{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border/60 bg-card/40 p-3">
      <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function KV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-[11px]">
      <span className="text-muted-foreground">{k}</span>
      <span className={`text-right ${mono ? "font-mono" : ""}`}>{v}</span>
    </div>
  );
}
