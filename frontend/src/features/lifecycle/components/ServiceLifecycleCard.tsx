import { useState } from "react";
import { Bug, Loader2, Rocket, ScanSearch, Waves } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/mlBackend";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { useLiveStore } from "@/shared/store/liveStore";
import type { InjectionKind, LiveServiceHealth } from "../types";
import { ACTION_LABEL, ACTION_TONE, PHASE_LABEL, PHASE_TONE, TONE_TEXT, VERDICT_LABEL } from "../lib/format";
import { LiveScoreChart } from "./LiveScoreChart";
import { Pill } from "./Pill";

type Action = InjectionKind | "check";

const INJECTIONS: { kind: Action; label: string; icon: typeof Rocket; hint: string }[] = [
  { kind: "deploy", label: "Deploy", icon: Rocket, hint: "Persistent shift plus a deployment change event" },
  { kind: "silent_change", label: "Silent", icon: Waves, hint: "Persistent shift with no change event" },
  { kind: "incident", label: "Incident", icon: Bug, hint: "Transient spike on a few metrics" },
  { kind: "check", label: "Check", icon: ScanSearch, hint: "Ask CADAL to validate this model now (operator triggered validity check)" },
];

const SEVERITY_STROKE = {
  watch: "var(--foreground)",
  warn: "var(--status-warn)",
  degrade: "var(--status-degrade)",
  critical: "var(--status-critical)",
} as const;

export function ServiceLifecycleCard({ service }: { service: LiveServiceHealth }) {
  const points = useLiveStore((s) => s.scores[service.serviceId]) ?? [];
  const lastDecision = useLiveStore((s) => s.decisions.find((d) => d.serviceId === service.serviceId));
  const [pending, setPending] = useState<Action | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const run = async (kind: Action) => {
    setPending(kind);
    setNote(null);
    try {
      if (kind === "check") await api.validityCheck(service.serviceId);
      else await api.inject(service.serviceId, kind);
    } catch (e) {
      // 409: a check is already running, which is what the presenter wants anyway
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setTimeout(() => setPending(null), 600);
    }
  };

  return (
    <Card className={cn("border-border/60 gap-3 py-4", service.alarm && "border-status-critical/50")}>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{service.displayName}</p>
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              {service.smdEntity} · model v{service.modelVersion}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            {service.phase !== "stable" && service.quarantineTrigger === "scheduled" ? (
              <Pill tone="neutral">Validity check</Pill>
            ) : (
              <Pill tone={PHASE_TONE[service.phase]}>{PHASE_LABEL[service.phase]}</Pill>
            )}
            <SeverityBadge severity={service.status} />
          </div>
        </div>

        <LiveScoreChart points={points} stroke={SEVERITY_STROKE[service.status]} />

        <p className="min-h-8 text-xs leading-4 text-muted-foreground">
          {lastDecision ? (
            <>
              <span className={cn("font-medium", TONE_TEXT[ACTION_TONE[lastDecision.action]])}>
                {VERDICT_LABEL[lastDecision.verdict] ?? lastDecision.verdict} → {ACTION_LABEL[lastDecision.action]}
              </span>{" "}
              <span className="line-clamp-1" title={lastDecision.reason}>
                {lastDecision.reason}
              </span>
            </>
          ) : (
            "No lifecycle decision yet."
          )}
        </p>

        <div className="grid grid-cols-4 gap-1.5">
          {INJECTIONS.map(({ kind, label, icon: Icon, hint }) => (
            <Button
              key={kind}
              size="sm"
              variant="outline"
              className="h-7 px-1.5 text-xs"
              title={hint}
              disabled={pending !== null}
              onClick={() => run(kind)}
            >
              {pending === kind ? <Loader2 className="size-3 animate-spin" /> : <Icon className="size-3" />}
              {label}
            </Button>
          ))}
        </div>
        {note && <p className="text-[11px] text-muted-foreground">{note}</p>}
      </CardContent>
    </Card>
  );
}
