import { useState } from "react";
import { Bug, Cpu, Loader2, Rocket, RotateCw, ScanSearch, Skull, Waves } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/mlBackend";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { useLiveStore } from "@/shared/store/liveStore";
import type { InjectionKind, LiveAction, LiveServiceHealth, QuarantineProgress } from "../types";
import { ACTION_LABEL, ACTION_TONE, PHASE_LABEL, PHASE_TONE, TONE_TEXT, VERDICT_LABEL } from "../lib/format";
import { LiveScoreChart } from "./LiveScoreChart";
import { Pill } from "./Pill";

type Action = InjectionKind | LiveAction | "check";

const INJECTIONS: { kind: Action; label: string; icon: typeof Rocket; hint: string }[] = [
  { kind: "deploy", label: "Deploy", icon: Rocket, hint: "Persistent shift plus a deployment change event" },
  { kind: "silent_change", label: "Silent", icon: Waves, hint: "Persistent shift with no change event" },
  { kind: "incident", label: "Incident", icon: Bug, hint: "Transient spike on a few metrics" },
  { kind: "restart", label: "Restart", icon: RotateCw, hint: "Rollout restart: deployment event plus a short spike, then back to normal" },
  { kind: "check", label: "Check", icon: ScanSearch, hint: "Ask CADAL to validate this model now (operator triggered validity check)" },
];

// Live mode: real scenarios on the cluster instead of synthetic injections into the telemetry.
const LIVE_ACTIONS: { kind: Action; label: string; icon: typeof Rocket; hint: string }[] = [
  { kind: "rollout", label: "Rollout", icon: Rocket, hint: "Real rolling update of this Deployment; the Kubernetes watcher sends a deployment change event" },
  { kind: "cpu_stress", label: "CPU", icon: Cpu, hint: "Chaos Mesh CPU stress on one pod for 3 minutes (an incident)" },
  { kind: "pod_kill", label: "Kill pod", icon: Skull, hint: "Chaos Mesh kills one pod; Kubernetes restarts it" },
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
  const live = useLiveStore((s) => s.health?.mode === "prometheus");

  const run = async (kind: Action) => {
    setPending(kind);
    setNote(null);
    try {
      if (kind === "check") await api.validityCheck(service.serviceId);
      else if (live) await api.live(service.serviceId, kind as LiveAction);
      else await api.inject(service.serviceId, kind as InjectionKind);
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
              {service.source ?? service.smdEntity} · model v{service.modelVersion}
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

        {service.phase !== "stable" && service.quarantine && service.quarantine.length > 0 && (
          <QuarantineBar progress={service.quarantine} />
        )}

        <p className="min-h-8 text-xs leading-4 text-muted-foreground">
          {lastDecision ? (
            <>
              <span className={cn("font-medium", TONE_TEXT[ACTION_TONE[lastDecision.action]])}>
                {VERDICT_LABEL[lastDecision.verdict] ?? lastDecision.verdict} → {ACTION_LABEL[lastDecision.action]}
              </span>{" "}
              {earlyPercent(lastDecision.evidence) !== null && (
                <span className="font-medium text-foreground">
                  decided early at {earlyPercent(lastDecision.evidence)}%{" "}
                </span>
              )}
              <span className="line-clamp-1" title={lastDecision.reason}>
                {lastDecision.reason}
              </span>
            </>
          ) : (
            "No lifecycle decision yet."
          )}
        </p>

        <div className={cn("grid gap-1.5", live ? "grid-cols-4" : "grid-cols-5")}>
          {(live ? LIVE_ACTIONS : INJECTIONS).map(({ kind, label, icon: Icon, hint }) => (
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

/** Share of the quarantine CADAL waited before an early decision, or null for a full-length one. */
function earlyPercent(evidence: Record<string, unknown>): number | null {
  const seen = Number(evidence.quarantine_events);
  const length = Number(evidence.quarantine_length);
  if (!evidence.early || !seen || !length) return null;
  return Math.round((100 * seen) / length);
}

function QuarantineBar({ progress }: { progress: QuarantineProgress }) {
  const pct = Math.min(100, (100 * progress.seen) / progress.length);
  return (
    <div className="space-y-1" title="Events collected in quarantine; ticks mark CADAL's early looks">
      <div className="relative h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-foreground/70 transition-[width]" style={{ width: `${pct}%` }} />
        {progress.looks.map((look) => (
          <span
            key={look}
            className="absolute top-0 h-full w-px bg-background"
            style={{ left: `${(100 * look) / progress.length}%` }}
          />
        ))}
      </div>
      <p className="font-mono text-[10px] text-muted-foreground">
        quarantine {progress.seen} / {progress.length} events
        {progress.looks.length > 0 &&
          ` · early looks at ${progress.looks.map((l) => Math.round((100 * l) / progress.length)).join("%, ")}%`}
      </p>
    </div>
  );
}
