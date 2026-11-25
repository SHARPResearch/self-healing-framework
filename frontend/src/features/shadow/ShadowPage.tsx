// frontend\src\features\shadow\ShadowPage.tsx
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Eye, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { ListTable, Pagination, TableToolbar, useListControls } from "@/shared/components/ListTable";
import type { ListColumn, SortState } from "@/shared/components/ListTable";
import { cn } from "@/lib/utils";
import { usePoll } from "@/hooks/usePoll";
import {
  fetchShadowMetrics,
  fetchShadowRecords,
  resolveShadow,
  type ApiShadowRow,
} from "@/lib/api";
import { formatClock, formatStamp, ago } from "@/features/decisions/lib/format";
import { prettyJson } from "@/features/decisions/lib/json";

const VERDICT_STYLE: Record<string, string> = {
  ACTION_WOULD_HAVE_HELPED: "bg-status-healthy/12 text-status-healthy border-status-healthy/40",
  ACTION_WOULD_HAVE_BEEN_UNNECESSARY:
    "bg-status-degrade/12 text-status-degrade border-status-degrade/40",
  HARMFUL: "bg-status-critical/12 text-status-critical border-status-critical/40",
  ANOMALY_STILL_ACTIVE: "bg-status-warn/12 text-status-warn border-status-warn/40",
  UNKNOWN: "bg-muted text-muted-foreground border-border",
};

const VERDICT_LABEL: Record<string, string> = {
  ACTION_WOULD_HAVE_HELPED: "would have helped",
  ACTION_WOULD_HAVE_BEEN_UNNECESSARY: "unnecessary",
  HARMFUL: "would have harmed",
  ANOMALY_STILL_ACTIVE: "anomaly still active",
  UNKNOWN: "unknown",
};

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) {
    return (
      <span className="rounded-full border border-border bg-muted px-1.5 py-px font-mono text-[9px] text-muted-foreground uppercase">
        observing
      </span>
    );
  }
  return (
    <span
      className={cn(
        "rounded-full border px-1.5 py-px font-mono text-[9px] font-medium uppercase",
        VERDICT_STYLE[verdict] ?? VERDICT_STYLE.UNKNOWN,
      )}
    >
      {VERDICT_LABEL[verdict] ?? verdict}
    </span>
  );
}

interface MetricRow {
  key: string;
  value: number;
}

/** Flatten one level of the metrics payload into numeric tiles. */
function flattenMetrics(metrics: Record<string, unknown> | null): MetricRow[] {
  if (!metrics) return [];
  const rows: MetricRow[] = [];
  for (const [key, value] of Object.entries(metrics)) {
    if (typeof value === "number" && Number.isFinite(value)) {
      rows.push({ key, value });
    } else if (value && typeof value === "object" && !Array.isArray(value)) {
      for (const [innerKey, innerValue] of Object.entries(
        value as Record<string, unknown>,
      )) {
        if (typeof innerValue === "number" && Number.isFinite(innerValue)) {
          rows.push({ key: `${key}.${innerKey}`, value: innerValue });
        }
      }
    }
  }
  return rows;
}

/**
 * Shadow mode (stage 5, §4). Every decision the policy matrix routed to
 * SHADOW_MODE lands in `shadow_records` with a counterfactual: what the
 * action *would* have done. The observer fills the verdict in later, which
 * is what makes "unnecessary action rate" measurable.
 */
export function ShadowPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<SortState | null>({
    key: "created_at",
    direction: "desc",
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const records = usePoll<ApiShadowRow[]>(() => fetchShadowRecords(200), {
    pollMs: 20000,
    key: "shadow",
  });
  const metrics = usePoll<Record<string, unknown>>(() => fetchShadowMetrics(), {
    pollMs: 20000,
    key: "shadow-metrics",
  });

  const all = records.data ?? [];
  const ordered = useMemo(() => {
    const pending = all.filter((r) => !r.verdict);
    const settled = all.filter((r) => r.verdict);
    return [...pending, ...settled];
  }, [all]);

  useEffect(() => setPage(1), [search, dateFrom, dateTo]);

  const table = useListControls({
    rows: ordered,
    search,
    searchValues: (row) => [
      row.service_id,
      row.candidate_action,
      row.risk,
      row.verdict ?? "",
      row.id,
      row.decision_id,
    ],
    dateField: (row) => row.created_at,
    dateFrom,
    dateTo,
    sort,
    sortValue: (row, key) => shadowSortValue(row, key),
    page,
    pageSize,
  });

  const columns = useMemo<ListColumn<ApiShadowRow>[]>(
    () => [
      {
        key: "service",
        header: "Service",
        sortValue: (row) => row.service_id,
        render: (row) => (
          <>
            <div className="font-medium">{row.service_id}</div>
            <div className="font-mono text-[9px] text-muted-foreground">{row.id}</div>
          </>
        ),
      },
      {
        key: "action",
        header: "Candidate action",
        sortValue: (row) => row.candidate_action,
        className: "font-mono text-[10px]",
        render: (row) => row.candidate_action,
      },
      {
        key: "confidence",
        header: "Conf",
        sortValue: (row) => row.confidence ?? 0,
        className: "text-right font-mono text-[10px]",
        render: (row) => `${Math.round((row.confidence ?? 0) * 100)}%`,
      },
      {
        key: "risk",
        header: "Risk",
        sortValue: (row) => row.risk,
        className: "font-mono text-[10px]",
        render: (row) => row.risk,
      },
      {
        key: "verdict",
        header: "Verdict",
        sortValue: (row) => row.verdict ?? "",
        render: (row) => <VerdictBadge verdict={row.verdict} />,
      },
      {
        key: "created_at",
        header: "Age",
        sortValue: (row) => row.created_at,
        className: "text-right font-mono text-[9px] text-muted-foreground",
        render: (row) => ago(row.created_at),
      },
    ],
    [],
  );

  const rows = table.visibleRows;
  const selected = rows.find((r) => r.id === selectedId) ?? rows[0] ?? null;
  const metricRows = flattenMetrics(metrics.data);

  const resolve = async (row: ApiShadowRow, naturally: boolean) => {
    setBusy(row.id);
    setActionError(null);
    try {
      await resolveShadow(row.id, naturally, naturally ? 60 : 300);
      records.refresh();
      metrics.refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const error = records.error ?? metrics.error ?? actionError;

  return (
    <AppShell pageTitle="Shadow mode">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Counterfactual observer</h2>
            <p className="text-sm text-muted-foreground">
              When confidence is not high enough to act, the engine records what
              it <em>would</em> have done instead of doing it. The observer later
              compares that against what actually happened.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7"
            onClick={() => {
              records.refresh();
              metrics.refresh();
            }}
            disabled={records.loading}
          >
            <RefreshCw className={cn("size-3.5", records.loading && "animate-spin")} />
          </Button>
        </div>

        {metricRows.length > 0 && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
            {metricRows.slice(0, 12).map((row) => (
              <div
                key={row.key}
                className="rounded-lg border border-border/60 px-3 py-2"
                title={row.key}
              >
                <p className="truncate text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
                  {row.key.replace(/[._]/g, " ")}
                </p>
                <p className="mt-0.5 font-mono text-lg leading-none">
                  {Number.isInteger(row.value) ? row.value : row.value.toFixed(3)}
                </p>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-status-critical/40 bg-status-critical/5 p-2.5 text-[11px]">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-status-critical" />
            <span>{error}</span>
          </div>
        )}

        {records.loading && all.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border/60 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Loading shadow records…
          </div>
        ) : (
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-2">
              <TableToolbar
                search={search}
                onSearchChange={setSearch}
                placeholder="Search service, action, verdict..."
                dateFrom={dateFrom}
                dateTo={dateTo}
                onDateFromChange={setDateFrom}
                onDateToChange={setDateTo}
              />
              <ListTable
                columns={columns}
                rows={rows}
                rowKey={(row) => row.id}
                error={error ?? actionError}
                emptyMessage="No shadow records match this filter."
                sort={sort}
                onSortChange={setSort}
                onRowClick={(row) => setSelectedId(row.id)}
                selectedKey={selected?.id ?? null}
                maxHeight="30rem"
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

            <aside className="space-y-3">
              {selected && (
                <>
                  <div className="rounded-xl border border-border/60 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">
                          {selected.service_id}
                        </p>
                        <p className="font-mono text-[10px] text-muted-foreground">
                          {selected.id}
                        </p>
                      </div>
                      <VerdictBadge verdict={selected.verdict} />
                    </div>
                    <dl className="mt-2 space-y-1 text-[11px]">
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Decision</dt>
                        <dd>
                          <Link
                            to={`/decisions/${encodeURIComponent(selected.decision_id)}`}
                            className="font-mono text-status-warn hover:underline"
                          >
                            open run →
                          </Link>
                        </dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Action</dt>
                        <dd className="font-mono">{selected.candidate_action}</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Confidence</dt>
                        <dd className="font-mono">
                          {Math.round((selected.confidence ?? 0) * 100)}%
                        </dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Risk</dt>
                        <dd className="font-mono">{selected.risk}</dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Recorded</dt>
                        <dd className="font-mono text-[10px]">
                          {formatStamp(selected.created_at)}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Observed</dt>
                        <dd className="font-mono text-[10px]">
                          {selected.observed_at ? formatClock(selected.observed_at) : "—"}
                        </dd>
                      </div>
                    </dl>
                    {selected.learning && (
                      <p className="mt-2 rounded-md bg-muted/60 px-2 py-1.5 text-[11px]">
                        {selected.learning}
                      </p>
                    )}
                  </div>

                  <div className="rounded-xl border border-border/60 p-3">
                    <p className="mb-1.5 flex items-center gap-1 text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                      <Sparkles className="size-3" />
                      Counterfactual
                    </p>
                    <p className="mb-1 text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
                      If the action had run
                    </p>
                    <pre className="max-h-32 overflow-auto rounded-md bg-muted/40 p-2 font-mono text-[10px] leading-relaxed">
                      {prettyJson(
                        selected.simulated_outcome ?? {
                          note: "no simulated outcome recorded",
                        },
                      )}
                    </pre>
                    {selected.actual_outcome && (
                      <>
                        <p className="mt-2 mb-1 text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
                          What actually happened
                        </p>
                        <pre className="max-h-32 overflow-auto rounded-md bg-muted/40 p-2 font-mono text-[10px] leading-relaxed">
                          {prettyJson(selected.actual_outcome)}
                        </pre>
                      </>
                    )}
                  </div>

                  {!selected.verdict && (
                    <div className="rounded-xl border border-border/60 p-3">
                      <p className="mb-2 flex items-center gap-1 text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                        <Eye className="size-3" />
                        Close it manually
                      </p>
                      <p className="mb-2 text-[10px] text-muted-foreground">
                        The observer normally fills this in once the anomaly
                        resolves. Use this only for a demo or to clear a stuck row.
                      </p>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="h-7 flex-1 text-[11px]"
                          disabled={busy === selected.id}
                          onClick={() => resolve(selected, true)}
                        >
                          {busy === selected.id && (
                            <Loader2 className="size-3 animate-spin" />
                          )}
                          Resolved by itself
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 flex-1 text-[11px]"
                          disabled={busy === selected.id}
                          onClick={() => resolve(selected, false)}
                        >
                          Needed help
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function shadowSortValue(row: ApiShadowRow, key: string): string | number | null {
  switch (key) {
    case "service":
      return row.service_id;
    case "action":
      return row.candidate_action;
    case "confidence":
      return row.confidence ?? 0;
    case "risk":
      return row.risk;
    case "verdict":
      return row.verdict ?? "";
    case "created_at":
      return row.created_at;
    default:
      return null;
  }
}
