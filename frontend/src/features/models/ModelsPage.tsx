import { useMemo, useState } from "react";
import { Info } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ModelRegistryTable } from "./components/ModelRegistryTable";
import { ModelDetailDialog } from "./components/ModelDetailDialog";
import { ModelFilterBar, type ModelFilter } from "./components/ModelFilterBar";
import { StatCard } from "@/features/dashboard/components/StatCard";
import { applyModelUpdate } from "./lib/modelActions";
import { LiveModelDetailDialog } from "./components/LiveModelDetailDialog";
import { api } from "@/lib/api";
import { useLiveStore } from "@/shared/store/liveStore";
import { pct } from "@/features/lifecycle/lib/format";
import { CROSS_ENTITY_MEAN_F1, TUNED_ENTITY_F1, modelRuns as initialModelRuns } from "./data/mockData";
import type { ModelRun } from "./types";

export function ModelsPage() {
  const ready = useLiveStore((s) => s.ready);
  const order = useLiveStore((s) => s.serviceOrder);
  const liveModels = useLiveStore((s) => s.models);
  const [mockRuns, setModelRuns] = useState<ModelRun[]>(initialModelRuns);
  const liveRuns = useMemo(() => order.map((id) => liveModels[id]).filter(Boolean), [order, liveModels]);
  const live = ready && liveRuns.length > 0;
  const modelRuns = live ? liveRuns : mockRuns;
  const [selected, setSelected] = useState<ModelRun | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [updatingIds, setUpdatingIds] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<ModelFilter>("ALL");

  const handleAction = (message: string) => {
    setLastAction(message);
    setSelected(null);
    setTimeout(() => setLastAction(null), 4000);
  };

  const replaceRun = (updated: ModelRun) => {
    setModelRuns((prev) => prev.map((r) => (r.runId === updated.runId ? updated : r)));
    setSelected((prev) => (prev?.runId === updated.runId ? updated : prev));
  };

  const handleUpdateRun = (run: ModelRun) => {
    setUpdatingIds((prev) => new Set(prev).add(run.runId));
    if (live) {
      const done = (message: string) => {
        setUpdatingIds((prev) => {
          const next = new Set(prev);
          next.delete(run.runId);
          return next;
        });
        setLastAction(message);
        setTimeout(() => setLastAction(null), 5000);
      };
      api
        .validityCheck(run.entityId)
        .then(() => done(`Validity check opened for ${run.serviceName}: CADAL observes one day of evidence before deciding`))
        .catch((e: Error) => done(`${run.serviceName}: ${e.message}`));
      return;
    }
    setTimeout(() => {
      const updated = applyModelUpdate(run);
      replaceRun(updated);
      setUpdatingIds((prev) => {
        const next = new Set(prev);
        next.delete(run.runId);
        return next;
      });
      setLastAction(`${run.serviceName} updated to v${updated.version} — drift resolved`);
      setTimeout(() => setLastAction(null), 4000);
    }, 1400);
  };

  const streaming = modelRuns.filter((r) => r.stage === "STREAMING").length;
  const meanAlarm = modelRuns.length ? modelRuns.reduce((a, r) => a + r.metrics.warnRate, 0) / modelRuns.length : 0;
  const totalVersions = modelRuns.reduce((a, r) => a + (r.versionCount ?? 1), 0);
  const openQueries = modelRuns.reduce((a, r) => a + (r.openQueries ?? 0), 0);
  const warmUp = modelRuns.filter((r) => r.stage === "WARM_UP").length;
  const totalDrift = modelRuns.reduce((sum, r) => sum + r.metrics.cumulativeDriftCount, 0);
  const evaluated = modelRuns.filter((r) => r.stage !== "WARM_UP");
  const avgF1 = evaluated.length
    ? evaluated.reduce((sum, r) => sum + r.metrics.evalF1, 0) / evaluated.length
    : 0;

  const visibleRuns = useMemo(() => {
    return modelRuns.filter((r) => {
      if (filter !== "ALL" && r.stage !== filter) return false;
      if (!search.trim()) return true;
      const q = search.trim().toLowerCase();
      return r.serviceName.toLowerCase().includes(q) || r.entityId.toLowerCase().includes(q);
    });
  }, [modelRuns, filter, search]);

  return (
    <AppShell pageTitle="Models">
      <div className="space-y-6">
        <div>
          <h2 className="text-base font-semibold">Model registry</h2>
          <p className="text-sm text-muted-foreground">
            {live
              ? `One smoothed PCA model per service with a per service POT threshold, versioned by the CADAL lifecycle. ${streaming} serving, ${totalDrift} lifecycle decisions.`
              : `One HalfSpaceTrees model per service, tracked in MLflow. ${streaming} streaming, ${totalDrift} drift events total.`}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {live ? (
            <>
              <StatCard
                label="Mean alarm rate"
                value={pct(meanAlarm)}
                deltaLabel="POT target 1.0% per model"
                deltaDirection={meanAlarm > 0.02 ? "up" : "down"}
                deltaTone={meanAlarm > 0.02 ? "negative" : "positive"}
              />
              <StatCard
                label="Lifecycle decisions"
                value={String(totalDrift)}
                deltaLabel="promote, roll back or ask"
                deltaDirection="up"
                deltaTone="positive"
              />
              <StatCard
                label="Model versions"
                value={String(totalVersions)}
                deltaLabel="incl. validity checkpoints"
                deltaDirection="up"
                deltaTone="positive"
              />
              <StatCard
                label="Awaiting operator"
                value={String(openQueries)}
                deltaLabel="ambiguous shifts, champion kept"
                deltaDirection={openQueries > 0 ? "up" : "down"}
                deltaTone={openQueries > 0 ? "negative" : "positive"}
              />
            </>
          ) : (
            <>
              <StatCard
                label="Avg F1 score"
                value={avgF1.toFixed(3)}
                deltaLabel="across streaming models"
                deltaDirection="up"
                deltaTone="positive"
              />
              <StatCard
                label="Drift events"
                value={String(totalDrift)}
                deltaLabel="cumulative, all models"
                deltaDirection={totalDrift > 0 ? "up" : "down"}
                deltaTone={totalDrift > 0 ? "negative" : "positive"}
              />
              <StatCard
                label="Streaming models"
                value={String(streaming)}
                deltaLabel={`of ${modelRuns.length} total`}
                deltaDirection="up"
                deltaTone="positive"
              />
              <StatCard
                label="Warm-up models"
                value={String(warmUp)}
                deltaLabel="not yet evaluated"
                deltaDirection={warmUp > 0 ? "up" : "down"}
                deltaTone={warmUp > 0 ? "negative" : "positive"}
              />
            </>
          )}
        </div>

        <ModelFilterBar
          search={search}
          onSearchChange={setSearch}
          filter={filter}
          onFilterChange={setFilter}
          onDeploy={() => handleAction("Deploy dispatched")}
        />

        {lastAction && (
          <Alert>
            <Info className="size-4" />
            <AlertTitle>Action dispatched</AlertTitle>
            <AlertDescription>
              {lastAction}
              {live ? "" : " (mock, nothing was sent)."}
            </AlertDescription>
          </Alert>
        )}

        <ModelRegistryTable
          runs={visibleRuns}
          updatingIds={updatingIds}
          onSelect={setSelected}
          onUpdate={handleUpdateRun}
          live={live}
        />

        {live ? (
          <Alert>
            <Info className="size-4" />
            <AlertTitle>Why there is no F1 column on live models</AlertTitle>
            <AlertDescription>
              <p>
                Live models run without labels, so precision, recall and F1 are measured offline on SMD's
                labels (see <span className="font-mono text-xs">ml-pipeline/RESULTS.md</span> and{" "}
                <span className="font-mono text-xs">RESULTS_COMPONENT2.md</span>). Online, each version's
                alarm threshold is calibrated per service by Peaks Over Threshold at a 1% risk, and the
                recent alarm rate shows whether a version still fits its service.
              </p>
            </AlertDescription>
          </Alert>
        ) : (
          <Alert>
            <Info className="size-4" />
            <AlertTitle>Why the F1 scores differ so much</AlertTitle>
            <AlertDescription>
              HST score distributions differ enough per service that one global threshold does not
              transfer. The best tuned entity reaches F1 {TUNED_ENTITY_F1.toFixed(4)}, but the mean
              across all 28 benchmark entities is {CROSS_ENTITY_MEAN_F1.toFixed(4)}, roughly 5x worse.
              Per entity percentile calibration is the validated fix, see{" "}
              <span className="font-mono text-xs">ml-pipeline/calibrate.py</span>.
            </AlertDescription>
          </Alert>
        )}
      </div>

      {live ? (
        <LiveModelDetailDialog
          run={selected}
          onClose={() => setSelected(null)}
          onAction={(message) => {
            setLastAction(message);
            setTimeout(() => setLastAction(null), 5000);
          }}
        />
      ) : (
        <ModelDetailDialog
          run={selected}
          onClose={() => setSelected(null)}
          onAction={handleAction}
          onRunUpdated={replaceRun}
        />
      )}
    </AppShell>
  );
}
