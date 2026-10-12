import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/shared/layout/AppShell";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { AnomalyEvidenceModal } from "./components/AnomalyEvidenceModal";
import { fetchDbAnomalies, type ApiDbAnomaly } from "@/lib/api";
import type { Severity } from "@/shared/types";

function toSeverity(sev?: string): Severity {
  if (sev === "high") return "critical";
  if (sev === "medium") return "warn";
  return "degrade";
}

type Filter = "all" | "captured" | "pending" | "failed";

export function AnomalyListPage() {
  const [items, setItems] = useState<ApiDbAnomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchDbAnomalies(200);
        if (!alive) return;
        setItems(list);
        setError(null);
      } catch (e: any) {
        if (!alive) return;
        setError(String(e.message ?? e));
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    const id = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const filtered = useMemo(() => {
    if (filter === "all") return items;
    return items.filter((i) => i.snapshot_status === filter);
  }, [items, filter]);

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
        </div>

        {/* Filter tabs */}
        <div className="flex flex-wrap gap-2">
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
                <th className="px-3 py-2 text-left">Detected</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-8 text-center text-muted-foreground"
                  >
                    Loading…
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-8 text-center text-destructive"
                  >
                    {error}
                  </td>
                </tr>
              )}
              {!loading && !error && filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
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
