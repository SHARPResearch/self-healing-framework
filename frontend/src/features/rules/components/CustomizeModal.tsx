import { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LockKeyhole } from "lucide-react";
import type {
  ApiRule,
  ApiRuleAppliesTo,
  ApiRuleCondition,
  ApiRuleGuardrails,
} from "@/lib/api";
import { GuardrailsEditor } from "./GuardrailsEditor";
import { RulePreview } from "./RulePreview";
import { ConditionReadOnly } from "./ConditionReadOnly";
import { toast } from "./toast";

interface Props {
  rule: ApiRule | null;
  onClose: () => void;
  onSave: (ruleId: string, patch: Record<string, unknown>) => Promise<void>;
  onClone: (rule: ApiRule) => void;
}

interface Draft {
  priority: number;
  enabled: boolean;
  description: string;
  applies_to: ApiRuleAppliesTo;
  guardrails: ApiRuleGuardrails;
}

const inputCls =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

/**
 * Level 2 — Customize modal.
 * Editable: priority, enabled, description, applies_to, guardrails.
 * Read-only: `when` and `then` (greyed out) — "Copy, don't touch."
 */
export function CustomizeModal({ rule, onClose, onSave, onClone }: Props) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!rule) {
      setDraft(null);
      return;
    }
    setDraft({
      priority: rule.priority,
      enabled: rule.enabled,
      description: rule.description,
      applies_to: {
        layers: [...rule.applies_to.layers],
        services: [...rule.applies_to.services],
        exclude_services: [...rule.applies_to.exclude_services],
      },
      guardrails: { ...rule.guardrails },
    });
  }, [rule]);

  const changed = useMemo(() => {
    if (!rule || !draft) return [] as string[];
    const keys: string[] = [];
    if (draft.priority !== rule.priority) keys.push("priority");
    if (draft.enabled !== rule.enabled) keys.push("enabled");
    if (draft.description !== rule.description) keys.push("description");
    if (JSON.stringify(draft.applies_to) !== JSON.stringify(rule.applies_to))
      keys.push("applies_to");
    if (JSON.stringify(draft.guardrails) !== JSON.stringify(rule.guardrails))
      keys.push("guardrails");
    return keys;
  }, [rule, draft]);

  if (!rule || !draft) return null;

  const patch = () => {
    const p: Record<string, unknown> = {};
    for (const k of changed) p[k] = (draft as unknown as Record<string, unknown>)[k];
    return p;
  };

  const handleSave = async () => {
    if (changed.length === 0) {
      onClose();
      return;
    }
    setSaving(true);
    try {
      await onSave(rule.id, patch());
      toast("Rule updated", "success", `${rule.id} · ${changed.join(", ")}`);
      onClose();
    } catch (e) {
      toast("Update failed", "error", String((e as Error).message));
    } finally {
      setSaving(false);
    }
  };

  const previewRule: ApiRule = {
    ...rule,
    priority: draft.priority,
    enabled: draft.enabled,
    description: draft.description,
    applies_to: draft.applies_to,
    guardrails: draft.guardrails,
  };

  return (
    <Dialog open={!!rule} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-base">{rule.id}</DialogTitle>
          <DialogDescription>
            Customize thresholds and safety settings. The rule's condition and
            action are managed by SHARP and shown read-only.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Editable fields */}
          <section className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Priority
              </span>
              <input
                type="number"
                value={draft.priority}
                onChange={(e) =>
                  setDraft({ ...draft, priority: Number(e.target.value) })
                }
                className={inputCls}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Enabled
              </span>
              <select
                value={draft.enabled ? "true" : "false"}
                onChange={(e) =>
                  setDraft({ ...draft, enabled: e.target.value === "true" })
                }
                className={inputCls}
              >
                <option value="true">Enabled</option>
                <option value="false">Disabled</option>
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Description
              </span>
              <input
                value={draft.description}
                onChange={(e) =>
                  setDraft({ ...draft, description: e.target.value })
                }
                className={inputCls}
              />
            </label>
          </section>

          <section>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Applies to
            </p>
            <div className="space-y-2">
              <CommaList
                label="Layers"
                value={draft.applies_to.layers}
                onChange={(layers) =>
                  setDraft({
                    ...draft,
                    applies_to: { ...draft.applies_to, layers },
                  })
                }
              />
              <CommaList
                label="Services"
                value={draft.applies_to.services}
                onChange={(services) =>
                  setDraft({
                    ...draft,
                    applies_to: { ...draft.applies_to, services },
                  })
                }
              />
              <CommaList
                label="Exclude services"
                value={draft.applies_to.exclude_services}
                onChange={(exclude_services) =>
                  setDraft({
                    ...draft,
                    applies_to: { ...draft.applies_to, exclude_services },
                  })
                }
              />
            </div>
          </section>

          <section>
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              Guardrails
            </p>
            <GuardrailsEditor
              guardrails={draft.guardrails}
              onChange={(guardrails) => setDraft({ ...draft, guardrails })}
            />
          </section>

          {/* Read-only shape */}
          <section className="rounded-lg border border-dashed border-border/70 bg-muted/20 p-3">
            <div className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
              <LockKeyhole className="size-3.5" />
              Read-only — condition &amp; action
            </div>
            <ConditionReadOnly when={rule.when as ApiRuleCondition} then={rule.then} />
            <p className="mt-2 text-[11px] text-muted-foreground">
              You can customize thresholds and settings. To change conditions,
              clone this rule as a custom rule.
            </p>
          </section>

          {/* Diff preview */}
          {changed.length > 0 && (
            <section>
              <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Preview ({changed.length} change{changed.length > 1 ? "s" : ""})
              </p>
              <RulePreview rule={previewRule} />
            </section>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onClone(rule)}>
            Clone as Custom Rule
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving || changed.length === 0}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CommaList({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <label className="flex items-center gap-2">
      <span className="w-32 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <input
        value={value.join(", ")}
        placeholder="comma,separated, or *"
        onChange={(e) =>
          onChange(
            e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          )
        }
        className={`${inputCls} flex-1 font-mono`}
      />
    </label>
  );
}
