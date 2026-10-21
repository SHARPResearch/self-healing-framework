import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { createCustomRule, deleteRule, patchRule, toggleRule, type ApiRule } from "@/lib/api";
import { useRules } from "./data/useRules";
import { RuleTable } from "./components/RuleTable";
import { CustomizeModal } from "./components/CustomizeModal";
import { RuleBuilderModal } from "./components/RuleBuilderModal";
import { ToastHost } from "./components/ToastHost";
import { toast } from "./components/toast";
import { RULE_TABS, type RuleTab } from "./types";

export function RuleListPage() {
  const [tab, setTab] = useState<RuleTab>("all");
  const { rules, loading, error, refetch } = useRules("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editing, setEditing] = useState<ApiRule | null>(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [builderSeed, setBuilderSeed] = useState<ApiRule | null>(null);

  const counts = useMemo(() => {
    const c: Record<RuleTab, number> = {
      all: rules.length,
      default: 0,
      custom: 0,
      templates: 0,
      archived: 0,
    };
    for (const r of rules) {
      if (r.is_template) c.templates++;
      else if (r.is_default) c.default++;
      else c.custom++;
      if (r.status === "ARCHIVED") c.archived++;
    }
    return c;
  }, [rules]);

  const visible = useMemo(() => {
    let list = rules;
    if (tab === "templates") list = rules.filter((r) => r.is_template);
    else if (tab === "default") list = rules.filter((r) => r.is_default && !r.is_template);
    else if (tab === "custom") list = rules.filter((r) => !r.is_default && !r.is_template);
    else if (tab === "archived") list = rules.filter((r) => r.status === "ARCHIVED");
    return [...list].sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
  }, [rules, tab]);

  const handleToggle = async (rule: ApiRule, next: boolean) => {
    setBusyId(rule.id);
    try {
      await toggleRule(rule.id, next);
      toast(next ? "Rule enabled" : "Rule disabled", "success", rule.id);
      refetch();
    } catch (e) {
      toast("Toggle failed", "error", String((e as Error).message));
    } finally {
      setBusyId(null);
    }
  };

  const handlePatch = async (ruleId: string, patch: Record<string, unknown>) => {
    await patchRule(ruleId, patch as never);
    refetch();
  };

  const handleDelete = async (rule: ApiRule) => {
    if (!window.confirm(`Delete custom rule "${rule.id}"? This cannot be undone.`))
      return;
    setBusyId(rule.id);
    try {
      await deleteRule(rule.id);
      toast("Rule deleted", "success", rule.id);
      refetch();
    } catch (e) {
      toast("Delete failed", "error", String((e as Error).message));
    } finally {
      setBusyId(null);
    }
  };

  const handleClone = (rule: ApiRule) => {
    setEditing(null);
    setBuilderSeed(rule);
    setBuilderOpen(true);
  };

  const handleCreate = async (
    payload: Record<string, unknown>,
    status: "DRAFT" | "ACTIVE",
  ) => {
    await createCustomRule({ ...payload, status } as never);
    refetch();
  };

  return (
    <AppShell pageTitle="Rules">
      <div className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Rules</h2>
            <p className="text-sm text-muted-foreground">
              Manage the rules that govern SHARP's decisions. Defaults ship with
              the system; custom rules are yours to build.
            </p>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setBuilderSeed(null);
              setBuilderOpen(true);
            }}
          >
            <Plus className="size-3.5" /> New Custom Rule
          </Button>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2">
          {RULE_TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => setTab(t.value)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                tab === t.value
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {t.label} ({counts[t.value]})
            </button>
          ))}
        </div>

        <RuleTable
          rules={visible}
          loading={loading}
          error={error}
          busyId={busyId}
          onToggle={handleToggle}
          onEdit={(r) => setEditing(r)}
          onClone={handleClone}
          onDelete={handleDelete}
        />

        <p className="text-[11px] text-muted-foreground">
          Click a rule id to open its detail + audit history.
        </p>
      </div>

      <CustomizeModal
        rule={editing}
        onClose={() => setEditing(null)}
        onSave={handlePatch}
        onClone={handleClone}
      />

      <RuleBuilderModal
        open={builderOpen}
        seed={builderSeed}
        onClose={() => {
          setBuilderOpen(false);
          setBuilderSeed(null);
        }}
        onSave={handleCreate}
      />

      <ToastHost />
    </AppShell>
  );
}
