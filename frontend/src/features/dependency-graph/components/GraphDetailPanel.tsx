import type { ReactNode } from "react";
import {
  ArrowRight,
  Activity,
  Cpu,
  HardDrive,
  Server,
  Zap,
  Database,
  ListFilter,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { Severity } from "@/shared/types";
import { identifyRootCause } from "../lib/identifyRootCause";
import type { GraphEdge, GraphNodeInput, PositionedNode } from "../types";
import type { ApiInfra, ApiApp } from "../data/useLiveGraph";

const STATUS_LABEL: Record<Severity, string> = {
  watch: "Healthy",
  warn: "Warning",
  degrade: "Degraded",
  critical: "Critical",
};

interface Props {
  selected: PositionedNode | null;
  graphNodes: GraphNodeInput[];
  graphEdges: GraphEdge[];
  infra?: ApiInfra;
  app?: ApiApp;
  anomaly?: {
    anomaly_score: number;
    severity: string;
    metric?: string;
    actual_value?: number;
    expected_value?: number;
  };
}

function DetailRow({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="font-mono text-[10px] tracking-wide text-muted-foreground/70 uppercase">
        {label}
      </span>
      <span
        className="font-mono text-xs font-medium"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </span>
    </div>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="mb-2 flex items-center gap-1.5 font-mono text-[10px] tracking-wide text-muted-foreground/70 uppercase">
      {children}
    </p>
  );
}

function Bar({ value, warn }: { value: number; warn: boolean }) {
  const pct = Math.min(100, Math.max(0, value * 100));
  const color = warn
    ? "bg-red-500"
    : pct > 60
      ? "bg-orange-500"
      : pct > 30
        ? "bg-yellow-500"
        : "bg-green-500";
  return (
    <div className="h-1.5 w-full rounded-full bg-secondary/60">
      <div
        className={`h-full rounded-full ${color} transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ─── Empty state (nothing selected) ─────────────────────────────────
function EmptyState({ graphNodes }: { graphNodes: GraphNodeInput[] }) {
  const counts: Record<Severity, number> = {
    watch: 0,
    warn: 0,
    degrade: 0,
    critical: 0,
  };
  for (const n of graphNodes) counts[n.status] += 1;
  const alerts = graphNodes.filter(
    (n) => n.status === "critical" || n.status === "warn",
  );

  return (
    <div className="flex w-72 shrink-0 flex-col gap-5 overflow-y-auto border-l border-border/60 p-4">
      <div>
        <SectionLabel>
          <Activity className="size-3" /> System health
        </SectionLabel>
        <div className="flex flex-col gap-2">
          {(["watch", "degrade", "warn", "critical"] as Severity[]).map((s) => (
            <div key={s} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: `var(--color-status-${s})` }}
                />
                <span className="text-xs text-muted-foreground">
                  {STATUS_LABEL[s]}
                </span>
              </div>
              <span
                className="font-mono text-sm font-semibold"
                style={{ color: `var(--color-status-${s})` }}
              >
                {counts[s]}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-border/60 pt-4">
        <SectionLabel>
          <Zap className="size-3" /> Active alerts
        </SectionLabel>
        {alerts.length === 0 ? (
          <p className="text-xs text-muted-foreground">No active alerts.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {alerts.map((s) => (
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
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {s.displayName}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <p className="text-[11px] text-muted-foreground/70">
        Click a node to inspect its health, metrics, and dependency edges.
      </p>
    </div>
  );
}

// ─── Selected node — full details ───────────────────────────────────
export function GraphDetailPanel({
  selected,
  graphNodes,
  graphEdges,
  infra,
  app,
  anomaly,
}: Props) {
  const navigate = useNavigate();

  if (!selected) return <EmptyState graphNodes={graphNodes} />;

  const rootCause = identifyRootCause(
    selected.serviceId,
    graphNodes,
    graphEdges,
  );
  const rootCauseNode = graphNodes.find(
    (n) => n.serviceId === rootCause.rootCauseId,
  );

  const dependencies = graphEdges
    .filter(
      (e) => e.source === selected.serviceId || e.target === selected.serviceId,
    )
    .map((e) => {
      const outgoing = e.source === selected.serviceId;
      const peerId = outgoing ? e.target : e.source;
      const peer = graphNodes.find((n) => n.serviceId === peerId);
      return peer ? { peer, outgoing, latencyMs: e.latencyMs } : null;
    })
    .filter((x): x is NonNullable<typeof x> => x !== null);

  // ─── Kubernetes / Infra ──────────────────────────────────────────
  const podsReady = infra?.ready_pods ?? 0;
  const podsTotal = infra?.pod_count ?? 0;
  const podsOk = podsReady === podsTotal && podsTotal > 0;
  const cpuPct = infra?.cpu.usage_pct ?? 0;
  const memPct = infra?.memory.pct ?? 0;
  const memUsed = infra?.memory.used_mb ?? 0;
  const memLimit = infra?.memory.limit_mb ?? 0;
  const restarts = infra?.restarts_last_5m ?? 0;
  const rxKbps = infra?.network.rx_kbps ?? 0;
  const txKbps = infra?.network.tx_kbps ?? 0;
  const nodeHost = infra?.node ?? "—";

  // ─── Application / APM ──────────────────────────────────────────
  const rps = app?.requests_per_sec ?? 0;
  const p50 = app?.latency_ms.p50 ?? 0;
  const p95 = app?.latency_ms.p95 ?? 0;
  const p99 = app?.latency_ms.p99 ?? 0;
  const errorRate = app?.error_rate ?? 0;
  const sc = app?.status_codes;
  const conns = app?.active_connections ?? 0;
  const dbP95 = app?.db_query_p95_ms ?? 0;
  const cacheHit = app?.cache_hit_rate ?? 0;

  return (
    <div className="flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-l border-border/60 p-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span
          className="size-2 rounded-full"
          style={{ background: `var(--color-status-${selected.status})` }}
        />
        <span className="text-sm font-semibold">{selected.displayName}</span>
      </div>

      {/* Core status */}
      <div className="flex flex-col gap-2.5">
        <DetailRow
          label="Status"
          value={STATUS_LABEL[selected.status]}
          accent={`var(--color-status-${selected.status})`}
        />
        <DetailRow label="Service ID" value={selected.serviceId} />
        {anomaly && (
          <>
            <DetailRow
              label="Anomaly"
              value={`${(anomaly.anomaly_score * 100).toFixed(0)}%`}
              accent={
                anomaly.anomaly_score >= 0.85
                  ? "var(--color-status-critical)"
                  : anomaly.anomaly_score >= 0.6
                    ? "var(--color-status-warn)"
                    : undefined
              }
            />
            {anomaly.metric && (
              <DetailRow
                label="Trigger"
                value={`${anomaly.actual_value?.toFixed(0)} / ${anomaly.expected_value?.toFixed(0)}`}
              />
            )}
          </>
        )}
      </div>

      {/* ─── Kubernetes / Infra ─────────────────────────────────── */}
      <div className="border-t border-border/60 pt-4">
        <SectionLabel>
          <Server className="size-3" /> Kubernetes
        </SectionLabel>
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[10px] tracking-wide text-muted-foreground/70 uppercase">
              Pods ready
            </span>
            <span
              className={`font-mono text-xs font-medium ${
                podsOk ? "text-green-600" : "text-orange-500"
              }`}
            >
              {podsReady} / {podsTotal}
            </span>
          </div>
          <DetailRow
            label="Restarts (5m)"
            value={String(restarts)}
            accent={restarts > 0 ? "var(--color-status-warn)" : undefined}
          />
          <DetailRow label="Node" value={nodeHost} />
        </div>
      </div>

      {/* ─── Resource usage ─────────────────────────────────────── */}
      {infra && (
        <div className="border-t border-border/60 pt-4">
          <SectionLabel>
            <Cpu className="size-3" /> Resources
          </SectionLabel>
          <div className="flex flex-col gap-3">
            <div>
              <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
                <span>CPU</span>
                <span className="font-mono">{(cpuPct * 100).toFixed(0)}%</span>
              </div>
              <Bar value={cpuPct} warn={cpuPct > 0.8} />
            </div>
            <div>
              <div className="mb-1 flex justify-between text-[10px] text-muted-foreground">
                <span>Memory</span>
                <span className="font-mono">
                  {memUsed} / {memLimit} MB ({(memPct * 100).toFixed(0)}%)
                </span>
              </div>
              <Bar value={memPct} warn={memPct > 0.8} />
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <DetailRow label="RX" value={`${rxKbps} kb/s`} />
              <DetailRow label="TX" value={`${txKbps} kb/s`} />
            </div>
          </div>
        </div>
      )}

      {/* ─── Application metrics ────────────────────────────────── */}
      {app && (
        <div className="border-t border-border/60 pt-4">
          <SectionLabel>
            <Database className="size-3" /> Application
          </SectionLabel>
          <div className="flex flex-col gap-2.5">
            <DetailRow label="RPS" value={rps.toFixed(1)} />
            <DetailRow label="P50" value={`${p50.toFixed(1)} ms`} />
            <DetailRow label="P95" value={`${p95.toFixed(1)} ms`} />
            <DetailRow
              label="P99"
              value={`${p99.toFixed(1)} ms`}
              accent={p99 > 500 ? "var(--color-status-warn)" : undefined}
            />
            <DetailRow
              label="Error rate"
              value={`${(errorRate * 100).toFixed(2)}%`}
              accent={
                errorRate > 0.05 ? "var(--color-status-critical)" : undefined
              }
            />
            {sc && (
              <div className="grid grid-cols-3 gap-1 text-xs">
                <div className="rounded border border-border/60 px-2 py-1 text-center">
                  <div className="font-mono text-[10px] text-muted-foreground">
                    2xx
                  </div>
                  <div className="font-mono font-semibold text-green-600">
                    {sc["2xx"]}
                  </div>
                </div>
                <div className="rounded border border-border/60 px-2 py-1 text-center">
                  <div className="font-mono text-[10px] text-muted-foreground">
                    4xx
                  </div>
                  <div className="font-mono font-semibold text-yellow-600">
                    {sc["4xx"]}
                  </div>
                </div>
                <div className="rounded border border-border/60 px-2 py-1 text-center">
                  <div className="font-mono text-[10px] text-muted-foreground">
                    5xx
                  </div>
                  <div
                    className={`font-mono font-semibold ${
                      sc["5xx"] > 0 ? "text-red-600" : "text-muted-foreground"
                    }`}
                  >
                    {sc["5xx"]}
                  </div>
                </div>
              </div>
            )}
            <DetailRow label="Connections" value={String(conns)} />
            <DetailRow label="DB P95" value={`${dbP95} ms`} />
            <DetailRow
              label="Cache hit"
              value={`${(cacheHit * 100).toFixed(0)}%`}
            />
          </div>
        </div>
      )}

      {/* ─── Dependencies ───────────────────────────────────────── */}
      <div className="border-t border-border/60 pt-4">
        <SectionLabel>
          <HardDrive className="size-3" /> Dependencies ({dependencies.length})
        </SectionLabel>
        {dependencies.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No direct dependencies.
          </p>
        ) : (
          <div className="flex flex-col gap-1.5">
            {dependencies.map(({ peer, outgoing, latencyMs }) => (
              <div
                key={peer.serviceId}
                className="flex items-center justify-between"
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">
                    {outgoing ? "→" : "←"}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: `var(--color-status-${peer.status})` }}
                  >
                    {peer.displayName}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {latencyMs}ms
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ─── Root cause ─────────────────────────────────────────── */}
      {selected.status !== "watch" && rootCauseNode && (
        <div className="border-t border-border/60 pt-4">
          <SectionLabel>
            <Zap className="size-3" /> Root cause
          </SectionLabel>
          {rootCause.isRootCause ? (
            <p className="text-xs text-muted-foreground">
              <span
                className="font-medium"
                style={{ color: `var(--color-status-${selected.status})` }}
              >
                {selected.displayName}
              </span>{" "}
              has no unhealthy downstream dependency — likely the root cause.
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Likely root cause:{" "}
              <span
                className="font-medium"
                style={{ color: `var(--color-status-${rootCauseNode.status})` }}
              >
                {rootCauseNode.displayName}
              </span>
              . {selected.displayName}'s score is a cascading symptom.
            </p>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => navigate(`/incidents?filter=${selected.serviceId}`)}
        className="mt-1 flex items-center gap-1.5 text-xs font-medium text-foreground/80 hover:text-foreground"
      >
        View incidents
        <ArrowRight className="size-3.5" />
      </button>
      {anomaly && (
        <>
          <button
            type="button"
            onClick={() =>
              navigate(
                `/anomalies?service=${encodeURIComponent(selected.serviceId)}`,
              )
            }
            className="mt-1 flex items-center gap-1.5 text-xs font-medium text-foreground/80 hover:text-foreground"
          >
            <ListFilter className="size-3.5" />
            View anomalies
          </button>
          <button
            type="button"
            onClick={() => {
              // anomalyId isn't in the current prop shape — pass it through
              window.dispatchEvent(
                new CustomEvent("open-anomaly", { detail: selected.serviceId }),
              );
            }}
            className="mt-1 flex items-center gap-1.5 text-xs font-medium text-foreground/80 hover:text-foreground"
          >
            View evidence
            <ArrowRight className="size-3.5" />
          </button>
        </>
      )}
    </div>
  );
}
