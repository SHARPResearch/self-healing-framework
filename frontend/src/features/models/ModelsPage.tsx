import { useState } from "react";
import { Info } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ModelRegistryTable } from "./components/ModelRegistryTable";
import { ModelDetailDialog } from "./components/ModelDetailDialog";
import { CROSS_ENTITY_MEAN_F1, TUNED_ENTITY_F1, modelRuns } from "./data/mockData";
import type { ModelRun } from "./types";

export function ModelsPage() {
  const [selected, setSelected] = useState<ModelRun | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);

  const handleAction = (message: string) => {
    setLastAction(message);
    setSelected(null);
    setTimeout(() => setLastAction(null), 4000);
  };

  const streaming = modelRuns.filter((r) => r.stage === "STREAMING").length;
  const totalDrift = modelRuns.reduce((sum, r) => sum + r.metrics.cumulativeDriftCount, 0);

  return (
    <AppShell pageTitle="Models">
      <div className="space-y-6">
        <div>
          <h2 className="text-base font-semibold">Model registry</h2>
          <p className="text-sm text-muted-foreground">
            One HalfSpaceTrees model per service, tracked in MLflow. {streaming} streaming,{" "}
            {totalDrift} drift events total.
          </p>
        </div>

        {lastAction && (
          <Alert>
            <Info className="size-4" />
            <AlertTitle>Action dispatched</AlertTitle>
            <AlertDescription>{lastAction} (mock, nothing was sent).</AlertDescription>
          </Alert>
        )}

        <ModelRegistryTable runs={modelRuns} onSelect={setSelected} />

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
      </div>

      <ModelDetailDialog run={selected} onClose={() => setSelected(null)} onAction={handleAction} />
    </AppShell>
  );
}
