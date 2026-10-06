// frontend/src/features/dependency-graph/DependencyGraphPage.tsx

import { AppShell } from "@/shared/layout/AppShell";
import { DependencyGraphCanvas } from "./components/DependencyGraphCanvas";
// import { graphEdges, graphNodes } from "./data/mockData";
import type { Severity } from "@/shared/types";
import { useLiveGraph } from "./data/useLiveGraph";

const LEGEND: { severity: Severity; label: string }[] = [
  { severity: "watch", label: "Healthy" },
  { severity: "degrade", label: "Degraded" },
  { severity: "warn", label: "Warning" },
  { severity: "critical", label: "Critical" },
];

export function DependencyGraphPage() {
  const { nodes, edges } = useLiveGraph();
  return (
    <AppShell pageTitle="Dependency graph">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">
              Service dependency graph
            </h2>
            <p className="text-sm text-muted-foreground">
              {nodes.length} services · {edges.length} dependencies. An arrow
              from A to B means A calls B, built from the{" "}
              <span className="font-mono text-xs">selfheal.io/upstreams</span>{" "}
              annotation in the real system. Click a node to inspect it and run
              a root-cause analysis.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {LEGEND.map(({ severity, label }) => (
              <div key={severity} className="flex items-center gap-1.5">
                <span
                  className="size-2 rounded-full"
                  style={{ background: `var(--color-status-${severity})` }}
                />
                <span className="text-xs text-muted-foreground">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <DependencyGraphCanvas />

        <p className="text-xs text-muted-foreground">
          Amber dashed edges point at a service that is currently critical, so
          the caller is at risk of cascading failure. Drag to pan, scroll or use
          the controls to zoom.
        </p>
      </div>
    </AppShell>
  );
}
