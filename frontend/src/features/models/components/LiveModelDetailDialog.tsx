import { useCallback, useEffect, useState } from "react";
import { Loader2, RotateCcw, ScanSearch, Undo2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api } from "@/lib/mlBackend";
import { refreshLive } from "@/hooks/useLiveConnection";
import { useLiveStore } from "@/shared/store/liveStore";
import { Pill } from "@/features/lifecycle/components/Pill";
import {
  ACTION_LABEL,
  ACTION_TONE,
  PHASE_LABEL,
  TRIGGER_LABEL,
  VERDICT_LABEL,
  pct,
} from "@/features/lifecycle/lib/format";
import type { ModelDetail, ModelRun } from "../types";

interface LiveModelDetailDialogProps {
  run: ModelRun | null;
  onClose: () => void;
  onAction: (message: string) => void;
}

const VERSION_TONE: Record<string, "good" | "neutral" | "info"> = {
  production: "good",
  archived: "neutral",
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-xs">{value}</span>
    </div>
  );
}

/** A served model's full lifecycle record from services/ml-backend: versions, decisions, controls. */
export function LiveModelDetailDialog({ run, onClose, onAction }: LiveModelDetailDialogProps) {
  const operator = useLiveStore((s) => s.operator) || "operator";
  const [detail, setDetail] = useState<ModelDetail | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const serviceId = run?.entityId;

  const load = useCallback(async () => {
    if (!serviceId) return;
    try {
      setDetail(await api.model(serviceId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [serviceId]);

  useEffect(() => {
    setDetail(null);
    setError(null);
    load();
  }, [load]);

  if (!run) return null;
  const m = detail ?? run;

  const act = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    setError(null);
    try {
      const message = await fn();
      await Promise.all([load(), refreshLive()]);
      onAction(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const rollback = () =>
    act("rollback", async () => {
      const res = await api.rollback(run.entityId, operator);
      return `${run.serviceName} rolled back to v${res.model.productionVersion}`;
    });
  const restore = (version: number) =>
    act(`v${version}`, async () => {
      await api.promote(run.entityId, operator, version);
      return `${run.serviceName} now serves v${version}`;
    });
  const validityCheck = () =>
    act("check", async () => {
      await api.validityCheck(run.entityId);
      return `Validity check opened for ${run.serviceName}: CADAL observes one day of evidence before deciding`;
    });

  const versions = detail ? [...detail.versions].reverse() : [];
  const decisions = detail ? detail.decisions.filter((d) => d.action !== "resume").slice(0, 8) : [];
  const shifts = Object.entries(m.rebaselined ?? {});

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {run.serviceName}
            <Pill tone="good">v{m.productionVersion ?? m.version} serving</Pill>
            {m.phase && <Pill tone={m.phase === "stable" ? "neutral" : "info"}>{PHASE_LABEL[m.phase]}</Pill>}
          </DialogTitle>
          <DialogDescription>
            <span className="font-mono">{run.entityId}</span> &bull; {m.detector} &bull; threshold by{" "}
            {m.thresholdMethod?.toUpperCase()} &bull; {m.versionCount} versions
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 sm:grid-cols-[1fr_2fr]">
          <section>
            <h4 className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">Serving</h4>
            <Row label="alarm_rate (recent)" value={pct(m.metrics.warnRate)} />
            <Row label="mean_score" value={m.metrics.rollingMeanScore.toFixed(3)} />
            <Row label="warm_up_rows" value={m.metrics.warmUpEvents.toLocaleString("en-US")} />
            <Row label="drift_decisions" value={String(m.metrics.cumulativeDriftCount)} />
            <Row label="open_queries" value={String(m.openQueries ?? 0)} />
            {shifts.length > 0 && (
              <>
                <h4 className="mt-4 mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
                  Re-baselined metrics
                </h4>
                {shifts.slice(0, 6).map(([k, v]) => (
                  <Row key={k} label={k} value={(v >= 0 ? "+" : "") + v.toFixed(3)} />
                ))}
              </>
            )}
          </section>

          <section>
            <h4 className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Version history
            </h4>
            {!detail ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            ) : (
              <ScrollArea className="h-48 pr-3">
                <ul className="space-y-2">
                  {versions.map((v) => (
                    <li key={v.version} className="flex items-start justify-between gap-3 text-xs">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium">v{v.version}</span>
                          <Pill tone={VERSION_TONE[v.status] ?? "info"}>{v.status}</Pill>
                          <span className="text-muted-foreground">{v.kind?.replace("_", " ")}</span>
                        </div>
                        <p className="line-clamp-2 text-muted-foreground" title={v.reason}>
                          {v.queryId ? `operator ${v.operator} answered ${v.queryId}. ` : ""}
                          {v.reason}
                        </p>
                      </div>
                      {v.status !== "production" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 shrink-0 px-2 text-xs"
                          disabled={busy !== null}
                          onClick={() => restore(v.version)}
                        >
                          {busy === `v${v.version}` ? <Loader2 className="size-3 animate-spin" /> : <Undo2 className="size-3" />}
                          Restore
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            )}
          </section>
        </div>

        <section>
          <h4 className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Lifecycle decisions
          </h4>
          {decisions.length === 0 ? (
            <p className="text-xs text-muted-foreground">No promotions, holds or questions yet.</p>
          ) : (
            <ul className="space-y-1.5">
              {decisions.map((d, i) => (
                <li key={`${d.step}-${i}`} className="flex items-start gap-2 text-xs">
                  <Pill tone={ACTION_TONE[d.action] ?? "neutral"} className="shrink-0">
                    {ACTION_LABEL[d.action] ?? d.action}
                  </Pill>
                  <span className="text-muted-foreground">
                    <span className="text-foreground">
                      {VERDICT_LABEL[d.verdict] ?? d.verdict} on {TRIGGER_LABEL[d.trigger] ?? d.trigger}
                    </span>{" "}
                    (step {d.step}): {d.reason}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {error && <p className="text-xs text-status-critical">{error}</p>}

        <DialogFooter>
          <Button variant="outline" size="sm" disabled={busy !== null} onClick={validityCheck}>
            {busy === "check" ? <Loader2 className="animate-spin" /> : <ScanSearch />}
            Validity check
          </Button>
          <Button variant="outline" size="sm" disabled={busy !== null} onClick={rollback}>
            {busy === "rollback" ? <Loader2 className="animate-spin" /> : <RotateCcw />}
            Roll back last promotion
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
