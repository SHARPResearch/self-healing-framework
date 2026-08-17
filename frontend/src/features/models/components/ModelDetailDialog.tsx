import { RotateCcw, TrendingUp } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { StageBadge } from "./StageBadge";
import type { ModelRun } from "../types";

interface ModelDetailDialogProps {
  run: ModelRun | null;
  onClose: () => void;
  onAction: (message: string) => void;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-mono text-xs">{value}</span>
    </div>
  );
}

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="font-mono text-xs font-medium">{value.toFixed(4)}</span>
      </div>
      <Progress value={value * 100} className="h-1.5" />
    </div>
  );
}

export function ModelDetailDialog({ run, onClose, onAction }: ModelDetailDialogProps) {
  if (!run) return null;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {run.serviceName}
            <StageBadge stage={run.stage} />
          </DialogTitle>
          <DialogDescription>
            <span className="font-mono">{run.entityId}</span> &bull; version {run.version} &bull; run{" "}
            <span className="font-mono">{run.runId.slice(0, 12)}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 sm:grid-cols-2">
          <section>
            <h4 className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Parameters
            </h4>
            <Row label="n_trees" value={String(run.params.nTrees)} />
            <Row label="height" value={String(run.params.height)} />
            <Row label="window_size" value={String(run.params.windowSize)} />
            <Row label="seed" value={String(run.params.seed)} />
            <Row label="adwin_delta" value={String(run.params.adwinDelta)} />
          </section>

          <section>
            <h4 className="mb-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Streaming metrics
            </h4>
            <Row label="rolling_mean_score" value={run.metrics.rollingMeanScore.toFixed(2)} />
            <Row label="cumulative_drift_count" value={String(run.metrics.cumulativeDriftCount)} />
            <Row label="warn_rate" value={run.metrics.warnRate.toFixed(2)} />
            <Row label="warm_up_events" value={run.metrics.warmUpEvents.toLocaleString("en-US")} />
            <Row label="throughput_eps" value={String(run.metrics.warmUpThroughputEps)} />
          </section>
        </div>

        <section className="space-y-3">
          <h4 className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Evaluation
          </h4>
          {run.stage === "WARM_UP" ? (
            <p className="text-xs text-muted-foreground">
              Not evaluated yet, still warming up.
            </p>
          ) : (
            <>
              <MetricBar label="Precision" value={run.metrics.evalPrecision} />
              <MetricBar label="Recall" value={run.metrics.evalRecall} />
              <MetricBar label="F1" value={run.metrics.evalF1} />
            </>
          )}
        </section>

        <DialogFooter>
          <Button variant="outline" size="sm" onClick={() => onAction(`Rolled back ${run.entityId}`)}>
            <RotateCcw className="mr-1.5 size-3.5" />
            Rollback
          </Button>
          <Button size="sm" onClick={() => onAction(`Promoted ${run.entityId} to production`)}>
            <TrendingUp className="mr-1.5 size-3.5" />
            Promote
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
