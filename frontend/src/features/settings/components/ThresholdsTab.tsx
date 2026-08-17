import { Info } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { Severity } from "@/shared/types";

const BANDS: { severity: Severity; range: string; action: string }[] = [
  { severity: "watch", range: "< 0.50", action: "Log only" },
  { severity: "warn", range: "0.50 - 0.70", action: "Alert and pre warm a replica" },
  { severity: "degrade", range: "0.70 - 0.85", action: "Circuit break, shift 50% traffic, scale +1" },
  { severity: "critical", range: "> 0.85", action: "Drain traffic, restart pod, roll back model" },
];

export function ThresholdsTab() {
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h3 className="text-base font-semibold">Severity thresholds</h3>
        <p className="text-sm text-muted-foreground">
          Anomaly score cutoffs the decision engine uses to pick a remediation level.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="warn-threshold">Warn at</Label>
          <Input id="warn-threshold" type="number" step="0.01" min="0" max="1" defaultValue="0.50" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="degrade-threshold">Degrade at</Label>
          <Input id="degrade-threshold" type="number" step="0.01" min="0" max="1" defaultValue="0.70" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="critical-threshold">Critical at</Label>
          <Input id="critical-threshold" type="number" step="0.01" min="0" max="1" defaultValue="0.85" />
        </div>
      </div>

      <div className="rounded-xl border border-border/60">
        {BANDS.map((band) => (
          <div
            key={band.severity}
            className="flex flex-wrap items-center gap-3 border-b border-border/60 p-3 last:border-0"
          >
            <SeverityBadge severity={band.severity} />
            <span className="font-mono text-xs text-muted-foreground">{band.range}</span>
            <span className="text-sm">{band.action}</span>
          </div>
        ))}
      </div>

      <Alert>
        <Info className="size-4" />
        <AlertTitle>These fixed cutoffs may not transfer across services</AlertTitle>
        <AlertDescription>
          HST score distributions differ per entity, so one global threshold performs far worse on
          services it was not tuned on. Per entity percentile calibration is implemented in{" "}
          <span className="font-mono text-xs">ml-pipeline/calibrate.py</span> and is the
          recommended replacement for these absolute values.
        </AlertDescription>
      </Alert>

      <Button size="sm">Save thresholds</Button>
    </div>
  );
}
