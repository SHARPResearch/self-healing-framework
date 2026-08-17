import { AppShell } from "@/shared/layout/AppShell";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { DependencyGraphCanvas } from "./components/DependencyGraphCanvas";
import type { Severity } from "@/shared/types";

const LEGEND: Severity[] = ["watch", "warn", "degrade", "critical"];

export function DependencyGraphPage() {
  return (
    <AppShell pageTitle="Dependency graph">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Service dependency graph</h2>
            <p className="text-sm text-muted-foreground">
              An arrow from A to B means A calls B. Built from the{" "}
              <span className="font-mono text-xs">selfheal.io/upstreams</span> annotation in the
              real system. Click a node to see its incidents.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {LEGEND.map((s) => (
              <SeverityBadge key={s} severity={s} />
            ))}
          </div>
        </div>

        <DependencyGraphCanvas />

        <p className="text-xs text-muted-foreground">
          Amber dashed edges point at a service that is currently critical, so the caller is at
          risk of cascading failure.
        </p>
      </div>
    </AppShell>
  );
}
