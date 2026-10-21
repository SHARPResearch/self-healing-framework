import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { X, ArrowRight } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { AnomalyEvidenceModal } from "./components/AnomalyEvidenceModal";
import { fetchDbAnomalies, type ApiDbAnomaly, type ApiDecision } from "@/lib/api";
import { useDecisions } from "@/features/decisions/data/useDecisions";
import type { Severity } from "@/shared/types";

function toSeverity(sev?: string): Severity {
  if (sev === "high") return "critical";
  if (sev === "medium") return "warn";
  return "degrade";
}

type Filter = "all" | "captured" | "pending" | "failed";

const POLL_MS = 3000;

export function AnomalyListPage() {
  const [items, setItems] = useState<ApiDbAnomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [nowTick, setNowTick] = useState(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Decisions for the same anomalies, joined client-side by anomaly_id so each
  // row can show its decision and deep-link to the decision detail modal.
  const { items: decisions } = useDecisions(POLL_MS);
  const decisionByAnomaly = useMemo(() => {
    const map = new Map<string, (typeof decisions)[number]>();
    for (const d of decisions) {
      if (!map.has(d.anomaly_id)) map.set(d.anomaly_id, d);
    }
    return map;
  }, [decisions]);

  // Deep-link filter: /anomalies?service=<id>. The param is consumed once into
  // local state and then cleared, so a later refresh (or back/forward) doesn't
  // silently re-apply it — the chip below is the source of truth thereafter.
  const [serviceFilter, setServiceFilter] = useState<string | null>(null);
  useEffect(() => {
    const svc = searchParams.get("service");
    if (svc) {
      setServiceFilter(svc);
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchDbAnomalies(200);
        if (!alive) return;
        setItems(list);
        setError(null);
        setLastUpdated(new Date());
      } catch (e: any) {
        if (!alive) return;
        setError(String(e.message ?? e));
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Re-render every second so "updated Xs ago" ticks without refetching.
  useEffect(() => {
    const id = setInterval(() => setNowTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const filtered = useMemo(() => {
    const byService = serviceFilter
      ? items.filter((i) => i.service_id === serviceFilter)
      : items;
    if (filter === "all") return byService;
    return byService.filter((i) => i.snapshot_status === filter);
  }, [items, filter, serviceFilter]);

  const counts = useMemo(() => {
    const c = { all: items.length, captured: 0, pending: 0, failed: 0 };
    for (const i of items) {
      if (i.snapshot_status === "captured") c.captured++;
      else if (i.snapshot_status === "pending") c.pending++;
      else if (i.snapshot_status === "failed") c.failed++;
    }
    return c;
  }, [items]);

  return (
    <AppShell pageTitle="Anomalies">
      <div className="space-y-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Anomaly events</h2>
            <p className="text-sm text-muted-foreground">
              Every anomaly persisted from the detection layer, with a telemetry
              window captured around it. Click a row to see the evidence.
            </p>
          </div>
          <LiveIndicator lastUpdated={lastUpdated} nowTick={nowTick} />
        </div>

        {/* Filter tabs */}
        <div className="flex flex-wrap items-center gap-2">
          {(["all", "captured", "pending", "failed"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                filter === f
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:bg-accent"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)} ({counts[f]})
            </button>
          ))}

          {serviceFilter && (
            <span className="ml-1 inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2 py-1 text-xs font-medium text-blue-600">
              Service: {serviceFilter}
              <button
                type="button"
                aria-label={`Clear ${serviceFilter} filter`}
                onClick={() => setServiceFilter(null)}
                className="rounded-full p-0.5 hover:bg-blue-500/20"
              >
                <X className="size-3" />
              </button>
            </span>
          )}
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-xl border border-border/60">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">Service</th>
                <th className="px-3 py-2 text-left">Severity</th>
                <th className="px-3 py-2 text-left">Metric</th>
                <th className="px-3 py-2 text-right">Actual</th>
                <th className="px-3 py-2 text-right">Expected</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Decision</th>
                <th className="px-3 py-2 text-left">Detected</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-3 py-8 text-center text-muted-foreground"
                  >
                    Loading…
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-3 py-8 text-center text-destructive"
                  >
                    {error}
                  </td>
                </tr>
              )}
              {!loading && !error && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-3 py-8 text-center text-muted-foreground"
                  >
                    No anomalies match this filter.
                  </td>
                </tr>
              )}
              {filtered.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => setOpenId(a.id)}
                  className="cursor-pointer border-t border-border/60 transition-colors hover:bg-accent/50"
                >
                  <td className="px-3 py-2">
                    <div className="font-medium">
                      {a.service_name ?? a.service_id}
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {a.id}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <SeverityBadge severity={toSeverity(a.severity)} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {a.metric ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
                    {a.actual_value?.toFixed(2) ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground">
                    {a.expected_value?.toFixed(2) ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <StatusPill status={a.snapshot_status} />
                  </td>
                  <td className="px-3 py-2">
                    <DecisionCell
                      decision={decisionByAnomaly.get(a.id)}
                      onView={(decisionId) =>
                        navigate(
                          `/decisions?focus=${encodeURIComponent(decisionId)}`,
                        )
                      }
                    />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {new Date(a.detected_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <AnomalyEvidenceModal
        anomalyId={openId}
        onClose={() => setOpenId(null)}
      />
    </AppShell>
  );
}

function LiveIndicator({
  lastUpdated,
  nowTick,
}: {
  lastUpdated: Date | null;
  nowTick: number;
}) {
  void nowTick; // re-render trigger for the relative-time label
  const ago = lastUpdated ? relativeTime(lastUpdated) : "—";
  return (
    <div className="flex shrink-0 items-center gap-2 rounded-full border border-green-500/30 bg-green-500/10 px-3 py-1">
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-green-500 opacity-75" />
        <span className="relative inline-flex size-2 rounded-full bg-green-500" />
      </span>
      <span className="text-xs font-medium text-green-600">Live</span>
      <span className="font-mono text-[10px] text-green-700/70">
        updated {ago}
      </span>
    </div>
  );
}

function relativeTime(d: Date): string {
  const secs = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (secs < 5) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    captured: "bg-green-500/15 text-green-600 border-green-500/30",
    pending: "bg-yellow-500/15 text-yellow-600 border-yellow-500/30",
    failed: "bg-red-500/15 text-red-600 border-red-500/30",
  };
  const cls = map[status] ?? "bg-secondary text-muted-foreground";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase ${cls}`}
    >
      {status}
    </span>
  );
}

const OUTCOME_STYLES: Record<string, string> = {
  AUTO_EXECUTE: "bg-green-500/10 text-green-600",
  SHADOW_MODE: "bg-blue-500/10 text-blue-600",
  HUMAN_LOOP: "bg-amber-500/10 text-amber-600",
  BLOCK: "bg-red-500/10 text-red-600",
  NO_RULE_MATCHED: "bg-zinc-500/10 text-zinc-600",
  UNVALIDATED: "bg-zinc-500/10 text-zinc-600",
};

function DecisionCell({
  decision,
  onView,
}: {
  decision: ApiDecision | undefined;
  onView: (decisionId: string) => void;
}) {
  if (!decision) {
    return (
      <span className="font-mono text-[10px] text-muted-foreground/70">
        no decision
      </span>
    );
  }

  const outcome = decision.policy.outcome ?? "UNVALIDATED";

  return (
    <button
      type="button"
      onClick={(e) => {
        // Don't also trigger the row's evidence modal.
        e.stopPropagation();
        onView(decision.decision_id);
      }}
      className="group flex flex-col items-start gap-0.5 text-left"
      title={`View decision ${decision.decision_id}`}
    >
      <span className="flex items-center gap-1.5">
        <span className="rounded-full bg-blue-500/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider text-blue-600">
          {decision.action}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-medium ${
            OUTCOME_STYLES[outcome] ?? ""
          }`}
        >
          {outcome}
        </span>
      </span>
      <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground group-hover:text-foreground">
        view decision
        <ArrowRight className="size-3" />
      </span>
    </button>
  );
}
