import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, X } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import { ListTable, Pagination, TableToolbar, useListControls } from "@/shared/components/ListTable";
import type { ListColumn, SortState } from "@/shared/components/ListTable";
import { AnomalyEvidenceModal } from "./components/AnomalyEvidenceModal";
import {
  fetchAnomaliesWithDecisions,
  type ApiAnomalyDecisionRow,
} from "@/lib/api";
import type { Severity } from "@/shared/types";

function toSeverity(sev?: string): Severity {
  if (sev === "high") return "critical";
  if (sev === "medium") return "warn";
  return "degrade";
}

type Filter = "all" | "captured" | "pending" | "failed";

const POLL_MS = 3000;

export function AnomalyListPage() {
  const [items, setItems] = useState<ApiAnomalyDecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [nowTick, setNowTick] = useState(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<SortState | null>({
    key: "detected_at",
    direction: "desc",
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const navigate = useNavigate();

  const [serviceFilter, setServiceFilter] = useState<string | null>(null);
  useEffect(() => {
    const svc = searchParams.get("service");
    if (svc) {
      setServiceFilter(svc);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const list = await fetchAnomaliesWithDecisions(500);
        if (!alive) return;
        setItems(list);
        setError(null);
        setLastUpdated(new Date());
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
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

  useEffect(() => {
    const id = setInterval(() => setNowTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => setPage(1), [search, dateFrom, dateTo, filter, serviceFilter]);

  const baseRows = useMemo(() => {
    const byService = serviceFilter
      ? items.filter((i) => i.service_id === serviceFilter)
      : items;
    if (filter === "all") return byService;
    return byService.filter((i) => i.snapshot_status === filter);
  }, [items, filter, serviceFilter]);

  const table = useListControls({
    rows: baseRows,
    search,
    searchValues: (row) => [
      row.id,
      row.service_id,
      row.service_name ?? "",
      row.metric ?? "",
      row.severity ?? "",
      row.decision_id ?? "",
      row.decision_action ?? "",
      row.decision_policy_outcome ?? "",
    ],
    dateField: (row) => row.detected_at,
    dateFrom,
    dateTo,
    sort,
    sortValue: (row, key) => anomalySortValue(row, key),
    page,
    pageSize,
  });

  const columns = useMemo<ListColumn<ApiAnomalyDecisionRow>[]>(
    () => [
      {
        key: "service",
        header: "Service",
        sortValue: (row) => row.service_name ?? row.service_id,
        render: (row) => (
          <>
            <div className="font-medium">{row.service_name ?? row.service_id}</div>
            <div className="font-mono text-[10px] text-muted-foreground">{row.id}</div>
          </>
        ),
      },
      {
        key: "severity",
        header: "Severity",
        sortValue: (row) => row.severity ?? "",
        render: (row) => <SeverityBadge severity={toSeverity(row.severity)} />,
      },
      {
        key: "metric",
        header: "Metric",
        sortValue: (row) => row.metric ?? "",
        className: "font-mono text-xs",
        render: (row) => row.metric ?? "—",
      },
      {
        key: "actual",
        header: "Actual",
        sortValue: (row) => row.actual_value ?? null,
        className: "text-right font-mono text-xs",
        render: (row) => row.actual_value?.toFixed(2) ?? "—",
      },
      {
        key: "expected",
        header: "Expected",
        sortValue: (row) => row.expected_value ?? null,
        className: "text-right font-mono text-xs text-muted-foreground",
        render: (row) => row.expected_value?.toFixed(2) ?? "—",
      },
      {
        key: "status",
        header: "Status",
        sortValue: (row) => row.snapshot_status ?? "",
        render: (row) => <StatusPill status={row.snapshot_status} />,
      },
      {
        key: "decision",
        header: "Decision",
        sortValue: (row) => row.decision_policy_outcome ?? "",
        render: (row) => (
          <DecisionCell
            row={row}
            onView={(decisionId) =>
              navigate(`/decisions?focus=${encodeURIComponent(decisionId)}`)
            }
          />
        ),
      },
      {
        key: "detected_at",
        header: "Detected",
        sortValue: (row) => row.detected_at,
        className: "font-mono text-xs text-muted-foreground",
        render: (row) => new Date(row.detected_at).toLocaleString(),
      },
    ],
    [navigate],
  );

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
              Every anomaly persisted from detection, joined server-side with
              its decision. Click a row to see the captured evidence.
            </p>
          </div>
          <LiveIndicator lastUpdated={lastUpdated} nowTick={nowTick} />
        </div>

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

        <TableToolbar
          search={search}
          onSearchChange={setSearch}
          placeholder="Search anomaly, service, metric, decision..."
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />
        <ListTable
          columns={columns}
          rows={table.visibleRows}
          rowKey={(row) => row.id}
          loading={loading}
          error={error}
          emptyMessage="No anomalies match this filter."
          sort={sort}
          onSortChange={setSort}
          onRowClick={(row) => setOpenId(row.id)}
        />
        <Pagination
          page={table.safePage}
          pageCount={table.pageCount}
          pageSize={pageSize}
          total={table.total}
          onPageChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </div>

      <AnomalyEvidenceModal
        anomalyId={openId}
        onClose={() => setOpenId(null)}
      />
    </AppShell>
  );
}

function anomalySortValue(row: ApiAnomalyDecisionRow, key: string): string | number | null {
  switch (key) {
    case "service":
      return row.service_name ?? row.service_id;
    case "severity":
      return row.severity ?? "";
    case "metric":
      return row.metric ?? "";
    case "actual":
      return row.actual_value ?? null;
    case "expected":
      return row.expected_value ?? null;
    case "status":
      return row.snapshot_status ?? "";
    case "decision":
      return row.decision_policy_outcome ?? "";
    case "detected_at":
      return row.detected_at;
    default:
      return null;
  }
}

function LiveIndicator({
  lastUpdated,
  nowTick,
}: {
  lastUpdated: Date | null;
  nowTick: number;
}) {
  void nowTick;
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
  row,
  onView,
}: {
  row: ApiAnomalyDecisionRow;
  onView: (decisionId: string) => void;
}) {
  if (!row.decision_id) {
    return (
      <span className="font-mono text-[10px] text-muted-foreground/70">
        no decision
      </span>
    );
  }

  const outcome = row.decision_policy_outcome ?? "UNVALIDATED";

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onView(row.decision_id as string);
      }}
      className="group flex flex-col items-start gap-0.5 text-left"
      title={`View decision ${row.decision_id}`}
    >
      <span className="flex items-center gap-1.5">
        <span className="rounded-full bg-blue-500/10 px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider text-blue-600">
          {row.decision_action ?? "NOOP"}
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
