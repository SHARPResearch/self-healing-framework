import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { DependencyGraph3D } from "./components/DependencyGraph3D";
import { ServiceList } from "./components/ServiceList";
import { graphEdges, graphNodes } from "./data/mockData";
import type { GraphNodeInput } from "./types";
import type { Severity } from "@/shared/types";

const LEGEND: Severity[] = ["watch", "warn", "degrade", "critical"];

export function DependencyGraphPage() {
  const navigate = useNavigate();
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const handleSelect = (node: GraphNodeInput) => {
    navigate(`/incidents?filter=${node.serviceId}`);
  };

  return (
    <AppShell pageTitle="Dependency graph">
      <div className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Service dependency graph</h2>
            <p className="text-sm text-muted-foreground">
              An arrow from A to B means A calls B. Built from the{" "}
              <span className="font-mono text-xs">selfheal.io/upstreams</span> annotation in the
              real system. Click a node, or a row in the list, to see its incidents.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {LEGEND.map((s) => (
              <SeverityBadge key={s} severity={s} />
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
          <DependencyGraph3D
            nodes={graphNodes}
            edges={graphEdges}
            hoveredId={hoveredId}
            onHoverChange={setHoveredId}
            onSelect={handleSelect}
          />
          <ServiceList
            nodes={graphNodes}
            hoveredId={hoveredId}
            onHoverChange={setHoveredId}
            onSelect={handleSelect}
          />
        </div>

        <p className="text-xs text-muted-foreground">
          Amber edges with moving particles point at a service that is currently critical, so the
          caller is at risk of cascading failure. Drag to orbit, scroll to zoom.
        </p>
      </div>
    </AppShell>
  );
}
