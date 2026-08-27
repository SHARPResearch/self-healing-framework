import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Severity } from "@/shared/types";
import { identifyRootCause } from "../lib/identifyRootCause";
import { graphEdges, graphNodes } from "../data/mockData";
import type { PositionedNode } from "../types";

const STATUS_LABEL: Record<Severity, string> = {
  watch: "Healthy",
  warn: "Warning",
  degrade: "Degraded",
  critical: "Critical",
};

// Deterministic, derived from the real mock anomalyScore -- not random --
// matching this repo's "no Math.random() in anything that renders" rule.
function deriveStats(node: PositionedNode) {
  const uptimePct = (100 - node.anomalyScore ** 2 * 12).toFixed(2);
  const p99Ms = Math.round(10 + node.anomalyScore * 380);
  const errorRatePct = (node.anomalyScore * 5).toFixed(2);
  const instancesReady = node.status === "watch" ? 3 : node.status === "critical" ? 1 : 2;
  return { uptimePct, p99Ms, errorRatePct, instancesReady };
}

function DetailRow({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="font-mono text-[10px] tracking-wide text-muted-foreground/70 uppercase">{label}</span>
      <span className="font-mono text-xs font-medium" style={accent ? { color: accent } : undefined}>
        {value}
      </span>
    </div>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="mb-2 font-mono text-[10px] tracking-wide text-muted-foreground/70 uppercase">{children}</p>
  );
}

interface GraphDetailPanelProps {
  selected: PositionedNode | null;
}

export function GraphDetailPanel({ selected }: GraphDetailPanelProps) {
  const navigate = useNavigate();

  if (!selected) {
    const counts: Record<Severity, number> = { watch: 0, warn: 0, degrade: 0, critical: 0 };
    for (const n of graphNodes) counts[n.status] += 1;
    const alertServices = graphNodes.filter((n) => n.status === "critical" || n.status === "warn");

    return (
      <div className="flex w-60 shrink-0 flex-col gap-5 border-l border-border/60 p-4">
        <div>
          <SectionLabel>System health</SectionLabel>
          <div className="flex flex-col gap-2">
            {(["watch", "degrade", "warn", "critical"] as Severity[]).map((s) => (
              <div key={s} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="size-1.5 rounded-full"
                    style={{ background: `var(--color-status-${s})` }}
                  />
                  <span className="text-xs text-muted-foreground">{STATUS_LABEL[s]}</span>
                </div>
                <span className="font-mono text-sm font-semibold" style={{ color: `var(--color-status-${s})` }}>
                  {counts[s]}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-border/60 pt-4">
          <SectionLabel>Active alerts</SectionLabel>
          {alertServices.length === 0 ? (
            <p className="text-xs text-muted-foreground">No active alerts.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {alertServices.map((s) => (
                <div
                  key={s.serviceId}
                  className="rounded-md border px-2.5 py-2"
                  style={{
                    borderColor: `color-mix(in oklch, var(--color-status-${s.status}) 30%, transparent)`,
                    background: `color-mix(in oklch, var(--color-status-${s.status}) 8%, transparent)`,
                  }}
                >
                  <p
                    className="font-mono text-[10px] font-semibold tracking-wide uppercase"
                    style={{ color: `var(--color-status-${s.status})` }}
                  >
                    {STATUS_LABEL[s.status]}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{s.displayName}</p>
                </div>
              ))}
            </div>
          )}
        </div>

        <p className="text-[11px] text-muted-foreground/70">
          Click a node to inspect its health, latency, and dependency edges.
        </p>
      </div>
    );
  }

  const stats = deriveStats(selected);
  const rootCause = identifyRootCause(selected.serviceId, graphNodes, graphEdges);
  const rootCauseNode = graphNodes.find((n) => n.serviceId === rootCause.rootCauseId);

  const dependencies = graphEdges
    .filter((e) => e.source === selected.serviceId || e.target === selected.serviceId)
    .map((e) => {
      const outgoing = e.source === selected.serviceId;
      const peerId = outgoing ? e.target : e.source;
      const peer = graphNodes.find((n) => n.serviceId === peerId)!;
      return { peer, outgoing, latencyMs: e.latencyMs };
    });

  return (
    <div className="flex w-60 shrink-0 flex-col gap-4 overflow-y-auto border-l border-border/60 p-4">
      <div className="flex items-center gap-2">
        <span className="size-2 rounded-full" style={{ background: `var(--color-status-${selected.status})` }} />
        <span className="text-sm font-semibold">{selected.displayName}</span>
      </div>

      <div className="flex flex-col gap-2.5">
        <DetailRow label="Status" value={STATUS_LABEL[selected.status]} accent={`var(--color-status-${selected.status})`} />
        <DetailRow label="Type" value="Service" />
        <DetailRow label="Uptime" value={`${stats.uptimePct}%`} />
        <DetailRow label="P99 latency" value={`${stats.p99Ms}ms`} />
        <DetailRow
          label="Error rate"
          value={`${stats.errorRatePct}%`}
          accent={selected.status === "critical" ? "var(--color-status-critical)" : undefined}
        />
        <DetailRow label="Instances" value={`${stats.instancesReady} / 3`} />
      </div>

      <div className="border-t border-border/60 pt-4">
        <SectionLabel>Dependencies</SectionLabel>
        {dependencies.length === 0 ? (
          <p className="text-xs text-muted-foreground">No direct dependencies.</p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {dependencies.map(({ peer, outgoing, latencyMs }) => (
              <div key={peer.serviceId} className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">{outgoing ? "→" : "←"}</span>
                  <span className="text-xs" style={{ color: `var(--color-status-${peer.status})` }}>
                    {peer.displayName}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-muted-foreground">{latencyMs}ms</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {selected.status !== "watch" && (
        <div className="border-t border-border/60 pt-4">
          <SectionLabel>Root cause analysis</SectionLabel>
          {rootCause.isRootCause ? (
            <p className="text-xs text-muted-foreground">
              <span className="font-medium" style={{ color: `var(--color-status-${selected.status})` }}>
                {selected.displayName}
              </span>{" "}
              has no unhealthy downstream dependency — it is the likely root cause, not a cascading symptom.
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Likely root cause:{" "}
              <span className="font-medium" style={{ color: `var(--color-status-${rootCauseNode!.status})` }}>
                {rootCauseNode!.displayName}
              </span>
              . {selected.displayName}'s elevated score is a cascading symptom of that dependency.
            </p>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => navigate(`/incidents?filter=${selected.serviceId}`)}
        className="mt-1 flex items-center gap-1.5 text-xs font-medium text-foreground/80 hover:text-foreground"
      >
        View incidents for this service
        <ArrowRight className="size-3.5" />
      </button>
    </div>
  );
}
