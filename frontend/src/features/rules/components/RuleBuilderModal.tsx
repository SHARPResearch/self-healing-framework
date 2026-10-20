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
import {
  Check,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  Loader2,
} from "lucide-react";
import type {
  ApiRule,
  ApiRuleAppliesTo,
  ApiRuleCondition,
  ApiRuleGuardrails,
  ApiRuleThen,
  ApiRuleValidateResult,
} from "@/lib/api";
import { validateRule } from "@/lib/api";
import { ConditionBuilder, MetricSuggestions } from "./ConditionBuilder";
import { ActionEditor } from "./ActionEditor";
import { GuardrailsEditor } from "./GuardrailsEditor";
import { RulePreview } from "./RulePreview";
import { KNOWN_LAYERS, slugify } from "../types";
import { toast } from "./toast";

interface Props {
  open: boolean;
  /** When set, the wizard starts pre-filled (Clone as Custom Rule). */
  seed?: ApiRule | null;
  onClose: () => void;
  onSave: (
    payload: Record<string, unknown>,
    status: "DRAFT" | "ACTIVE",
  ) => Promise<void>;
}

const STEPS = ["Basics", "Conditions", "Action", "Guardrails"] as const;
type Step = 0 | 1 | 2 | 3;

const inputCls =
  "h-8 w-full rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30";

interface Draft {
  id: string;
  description: string;
  priority: number;
  layers: string[];
  when: ApiRuleCondition;
  then: ApiRuleThen;
  guardrails: ApiRuleGuardrails;
  parent_rule_id: string | null;
}

function blankDraft(): Draft {
  return {
    id: "",
    description: "",
    priority: 100,
    layers: [],
    when: {
      all: [{ metric: "anomaly.score", op: ">=", value: 0.7 }],
    } as ApiRuleCondition,
    then: {
      action: "RESTART_POD",
      params: {
        namespace: "{{ service.namespace }}",
        selector: "app={{ service.id }}",
      },
      base_confidence: 0.8,
      base_risk: "MEDIUM",
    },
    guardrails: {
      cooldown_seconds: 300,
      max_per_hour: 3,
      idempotency_key: null,
    },
    parent_rule_id: null,
  };
}

function draftFrom(seed: ApiRule): Draft {
  return {
    id: `${seed.id}_copy`,
    description: seed.description,
    priority: seed.priority,
    layers: [...seed.applies_to.layers],
    when: structuredClone(seed.when) as ApiRuleCondition,
    then: structuredClone(seed.then) as ApiRuleThen,
    guardrails: { ...seed.guardrails },
    parent_rule_id: seed.id,
  };
}

export function RuleBuilderModal({ open, seed, onClose, onSave }: Props) {
  const [step, setStep] = useState<Step>(0);
  const [draft, setDraft] = useState<Draft>(blankDraft);
  const [idTouched, setIdTouched] = useState(false);
  const [validation, setValidation] = useState<ApiRuleValidateResult | null>(
    null,
  );
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep(0);
    setIdTouched(false);
    setValidation(null);
    setDraft(seed ? draftFrom(seed) : blankDraft());
  }, [open, seed]);

  // Auto-slug the id from the description until the user edits the id directly.
  useEffect(() => {
    if (idTouched) return;
    if (!draft.description) return;
    const slug = slugify(draft.description);
    if (slug && slug !== draft.id) setDraft((d) => ({ ...d, id: slug }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.description, idTouched]);

  const payload = useMemo<Record<string, unknown>>(
    () => ({
      id: draft.id,
      description: draft.description,
      priority: draft.priority,
      when: draft.when,
      then: draft.then,
      guardrails: draft.guardrails,
      applies_to: {
        layers: draft.layers,
        services: ["*"],
        exclude_services: [],
      } satisfies ApiRuleAppliesTo,
      tags: [],
      parent_rule_id: draft.parent_rule_id,
    }),
    [draft],
  );

  const previewRule = payload as unknown as ApiRule;

  const testRule = async () => {
    setTesting(true);
    try {
      const result = await validateRule(
        draft.id || "draft_rule",
        payload,
        true,
      );
      setValidation(result);
      if (!result.valid) {
        toast("Validation failed", "error", result.errors[0]);
      } else if (result.match_preview) {
        toast("Test complete", "success", result.match_preview.message);
      } else {
        toast("Rule is valid", "success");
      }
    } catch (e) {
      toast("Test failed", "error", String((e as Error).message));
    } finally {
      setTesting(false);
    }
  };

  const activate = async () => {
    setSaving(true);
    try {
      const result = await validateRule(
        draft.id || "draft_rule",
        payload,
        false,
      );
      setValidation(result);
      if (!result.valid) {
        toast("Cannot activate", "error", result.errors[0]);
        return;
      }
      await onSave(payload, "ACTIVE");
      toast("Custom rule activated", "success", draft.id);
      onClose();
    } catch (e) {
      toast("Save failed", "error", String((e as Error).message));
    } finally {
      setSaving(false);
    }
  };

  const saveDraft = async () => {
    setSaving(true);
    try {
      await onSave(payload, "DRAFT");
      toast("Saved as draft", "success", draft.id);
      onClose();
    } catch (e) {
      toast("Save failed", "error", String((e as Error).message));
    } finally {
      setSaving(false);
    }
  };

  const canAdvance =
    step === 0 ? draft.id.length > 0 && draft.description.length > 0 : true;

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[96vh] max-w-6xl overflow-y-auto sm:max-w-6xl">
        <DialogHeader>
          <DialogTitle>New Custom Rule</DialogTitle>
          <DialogDescription>
            Build a rule from scratch. It is validated before activation —
            nothing is saved until it passes.
          </DialogDescription>
        </DialogHeader>

        <MetricSuggestions />

        {/* Step indicator */}
        <ol className="flex items-center gap-2">
          {STEPS.map((label, i) => {
            const active = i === step;
            const done = i < step;
            return (
              <li key={label} className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setStep(i as Step)}
                  className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    active
                      ? "border-foreground bg-foreground text-background"
                      : done
                        ? "border-green-500/40 bg-green-500/10 text-green-600"
                        : "border-border text-muted-foreground"
                  }`}
                >
                  {done ? <Check className="size-3" /> : <span>{i + 1}</span>}
                  {label}
                </button>
                {i < STEPS.length - 1 && (
                  <ChevronRight className="size-3.5 text-muted-foreground/50" />
                )}
              </li>
            );
          })}
        </ol>

        {/* Steps */}
        <div className="min-h-[280px]">
          {step === 0 && (
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Description
                </span>
                <input
                  value={draft.description}
                  placeholder="Kill pod if memory > 95% and disk I/O high"
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                  className={inputCls}
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Rule ID (auto-generated from description)
                </span>
                <input
                  value={draft.id}
                  onChange={(e) => {
                    setIdTouched(true);
                    setDraft({ ...draft, id: slugify(e.target.value) });
                  }}
                  className={`${inputCls} font-mono`}
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Priority (higher = evaluated first)
                </span>
                <input
                  type="number"
                  value={draft.priority}
                  onChange={(e) =>
                    setDraft({ ...draft, priority: Number(e.target.value) })
                  }
                  className={`${inputCls} w-40`}
                />
              </label>
              <div>
                <span className="mb-1.5 block text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Layer applicability
                </span>
                <div className="flex flex-wrap gap-2">
                  {KNOWN_LAYERS.map((layer) => {
                    const on = draft.layers.includes(layer);
                    return (
                      <button
                        key={layer}
                        type="button"
                        onClick={() =>
                          setDraft({
                            ...draft,
                            layers: on
                              ? draft.layers.filter((l) => l !== layer)
                              : [...draft.layers, layer],
                          })
                        }
                        className={`rounded-full border px-3 py-1 font-mono text-xs capitalize transition-colors ${
                          on
                            ? "border-foreground bg-foreground text-background"
                            : "border-border text-muted-foreground hover:bg-accent"
                        }`}
                      >
                        {layer}
                      </button>
                    );
                  })}
                </div>
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Empty = every layer.
                </p>
              </div>
            </div>
          )}

          {step === 1 && (
            <ConditionBuilder
              value={draft.when}
              onChange={(when) => setDraft({ ...draft, when })}
            />
          )}

          {step === 2 && (
            <ActionEditor
              then={draft.then}
              onChange={(then) => setDraft({ ...draft, then })}
            />
          )}

          {step === 3 && (
            <GuardrailsEditor
              guardrails={draft.guardrails}
              onChange={(guardrails) => setDraft({ ...draft, guardrails })}
            />
          )}
        </div>

        {/* Validation result */}
        {validation && (
          <div
            className={`rounded-lg border p-3 text-xs ${
              validation.valid
                ? "border-green-500/30 bg-green-500/5"
                : "border-red-500/30 bg-red-500/5"
            }`}
          >
            {validation.valid ? (
              <p className="text-green-600">
                {validation.match_preview?.message ?? "Rule is valid."}
              </p>
            ) : (
              <ul className="list-disc space-y-0.5 pl-4 text-red-600">
                {validation.errors.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
            {validation.warnings?.length > 0 && (
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-amber-600">
                {validation.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Live preview */}
        <div>
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Live preview
          </p>
          <RulePreview rule={previewRule} />
        </div>

        <DialogFooter className="justify-between gap-2 sm:justify-between">
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={step === 0}
              onClick={() => setStep((s) => (s - 1) as Step)}
            >
              <ChevronLeft className="size-3.5" /> Back
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={step === 3 || !canAdvance}
              onClick={() => setStep((s) => (s + 1) as Step)}
            >
              Next <ChevronRight className="size-3.5" />
            </Button>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={testRule}
              disabled={testing}
            >
              {testing ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <FlaskConical className="size-3.5" />
              )}
              Test Rule
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={saveDraft}
              disabled={saving}
            >
              Save as Draft
            </Button>
            <Button size="sm" onClick={activate} disabled={saving}>
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : null}
              Activate
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
