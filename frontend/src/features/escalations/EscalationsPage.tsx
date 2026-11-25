// frontend\src\features\escalations\EscalationsPage.tsx
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  BellRing,
  Check,
  Loader2,
  RefreshCw,
  Send,
  Timer,
  X,
} from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ListTable, Pagination, TableToolbar, useListControls } from "@/shared/components/ListTable";
import type { ListColumn, SortState } from "@/shared/components/ListTable";
import { cn } from "@/lib/utils";
import { usePoll } from "@/hooks/usePoll";
import {
  acknowledgeEscalation,
  fetchEscalations,
  fireEscalation,
  type ApiEscalationAttempt,
  type ApiEscalationRow,
} from "@/lib/api";
import { formatClock, formatStamp, ago } from "@/features/decisions/lib/format";
import { asJson } from "@/features/decisions/lib/json";

const STATUS_STYLE: Record<string, string> = {
  PENDING: "bg-status-warn/12 text-status-warn border-status-warn/40",
  AWAITING_HUMAN: "bg-status-escalated/12 text-status-escalated border-status-escalated/40",
  RESOLVED: "bg-status-healthy/12 text-status-healthy border-status-healthy/40",
  MANUAL_REQUIRED: "bg-status-critical/12 text-status-critical border-status-critical/40",
};

/** The three attempts the worker fires, from escalation/README.md §1. */
const ATTEMPT_PLAN = [
  { attempt: 1, at: "T+0", template: "Initial" },
  { attempt: 2, at: "T+5m", template: "Reminder" },
  { attempt: 3, at: "T+15m", template: "Final failure" },
] as const;

const FILTERS = ["ALL", "PENDING", "AWAITING_HUMAN", "RESOLVED", "MANUAL_REQUIRED"] as const;
type Filter = (typeof FILTERS)[number];

function StatusBadge({ status }: { status: string }) {  return (
    <span
      className={cn(
        "rounded-full border px-1.5 py-px font-mono text-[9px] font-medium uppercase",
        STATUS_STYLE[status] ?? "border-border bg-muted text-muted-foreground",
      )}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function AttemptDots({ attempts, max }: { attempts: number; max: number }) {
  return (
    <span className="flex items-center gap-1" title={`${attempts} of ${max} attempts sent`}>
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "size-1.5 rounded-full",
            i < attempts ? "bg-status-escalated" : "bg-border",
          )}
        />
      ))}
    </span>
  );
}

/**
 * Human-in-the-loop queue (stage 6). Lists every escalation row, shows the
 * three-attempt delivery plan with what actually went out, and lets the
 * operator approve or reject — which is what `POST /ack` records.
 */
export function EscalationsPage() {
  const [filter, setFilter] = useState<Filter>("ALL");
  const [actor, setActor] = useState("operator");
  const [note, setNote] = useState("");
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

  const { data, loading, error, refresh } = usePoll<ApiEscalationRow[]>(
    () => fetchEscalations({ limit: 200 }),
    { pollMs: 15000, key: "escalations" },
  );

  const all = data ?? [];
  const counts = useMemo(() => {
    const acc: Record<string, number> = {
      PENDING: 0,
      AWAITING_HUMAN: 0,
      RESOLVED: 0,
      MANUAL_REQUIRED: 0,
    };
    for (const row of all) acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, [all]);

  const statusRows = useMemo(
    () => (filter === "ALL" ? all : all.filter((r) => r.status === filter)),
    [all, filter],
  );

  useEffect(() => setPage(1), [search, dateFrom, dateTo, filter]);

  const table = useListControls({
    rows: statusRows,
    search,
    searchValues: (row) => [
      row.id,
      row.service_id,
      row.status,
      row.decision_id,
      row.anomaly_id,
      row.failure_report ?? "",
    ],
    dateField: (row) => row.created_at,
    dateFrom,
    dateTo,
    sort,
    sortValue: (row, key) => escalationSortValue(row, key),
    page,
    pageSize,
  });

  const columns = useMemo<ListColumn<ApiEscalationRow>[]>(
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
        key: "status",
        header: "Status",
        sortValue: (row) => row.status,
        render: (row) => <StatusBadge status={row.status} />,
      },
      {
        key: "attempt",
        header: "Attempts",
        sortValue: (row) => row.attempt,
        render: (row) => (
          <div className="flex items-center gap-1.5">
            <AttemptDots attempts={row.attempt} max={row.max_attempts} />
            <span className="font-mono text-[9px] text-muted-foreground">
              {row.attempt}/{row.max_attempts}
            </span>
          </div>
        ),
      },
      {
        key: "next_attempt_at",
        header: "Next",
        sortValue: (row) => row.next_attempt_at ?? "",
        className: "font-mono text-[10px] text-muted-foreground",
        render: (row) =>
          terminal(row.status)
            ? "—"
            : row.next_attempt_at
              ? `${formatClock(row.next_attempt_at)} (${ago(row.next_attempt_at)})`
              : "—",
      },
      {
        key: "created_at",
        header: "Created",
        sortValue: (row) => row.created_at,
        className: "text-right font-mono text-[10px] text-muted-foreground",
        render: (row) => formatClock(row.created_at),
      },
    ],
    [],
  );

  const rows = table.visibleRows;
  const selected =
    rows.find((r) => r.id === selectedId) ?? rows[0] ?? null;

  // JSONB columns arrive as encoded strings from the engine — decode once.
  const selectedAttempts = selected
    ? asJson<ApiEscalationAttempt[]>(selected.notifications, [])
    : [];
  const selectedResponse = selected
    ? asJson<{
        decision?: string;
        by?: string;
        at?: string;
        note?: string;
        execution?: {
          status?: string;
          message?: string;
          action?: string;
          executed_at?: string;
        } | null;
      } | null>(selected.response, null)
    : null;

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusy(id);
    setActionError(null);
    try {
      await fn();
      refresh();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const ack = (row: ApiEscalationRow, decision: "APPROVED" | "REJECTED") =>
    act(row.id, () => acknowledgeEscalation(row.id, decision, actor || "operator", note));

  const fire = (row: ApiEscalationRow) => act(row.id, () => fireEscalation(row.id));

  const terminal = (status: string) =>
    status === "RESOLVED" || status === "MANUAL_REQUIRED";

  return (
    <AppShell pageTitle="Escalations">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Human in the loop</h2>
            <p className="text-sm text-muted-foreground">
              Every <span className="font-mono">HUMAN_LOOP</span> outcome becomes
              a persistent escalation. The worker fires three Gmail attempts at
              T+0, T+5m and T+15m; acknowledging one stops the schedule.
              Approving also runs the action through the executor, and the
              result is recorded against the escalation.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              Operator
              <Input
                value={actor}
                onChange={(e) => setActor(e.target.value)}
                className="h-7 w-32 text-xs"
                aria-label="Operator name recorded with the acknowledgement"
              />
            </label>
            <Button
              size="sm"
              variant="outline"
              className="h-7"
              onClick={refresh}
              disabled={loading}
            >
              <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(
            [
              ["PENDING", "Not sent yet"],
              ["AWAITING_HUMAN", "Waiting on a human"],
              ["RESOLVED", "Acknowledged"],
              ["MANUAL_REQUIRED", "Attempts exhausted"],
            ] as const
          ).map(([key, label]) => (
            <div key={key} className="rounded-lg border border-border/60 px-3 py-2">
              <p className="text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
                {label}
              </p>
              <p className="mt-0.5 font-mono text-lg leading-none">
                {counts[key] ?? 0}
              </p>
            </div>
          ))}
        </div>

        {(error || actionError) && (
          <div className="flex items-start gap-2 rounded-lg border border-status-critical/40 bg-status-critical/5 p-2.5 text-[11px]">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-status-critical" />
            <span>{actionError ?? error}</span>
          </div>
        )}

        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-[10px] font-medium",
                filter === f
                  ? "border-foreground/30 bg-accent text-accent-foreground"
                  : "border-border/60 text-muted-foreground hover:text-foreground",
              )}
            >
              {f.replace("_", " ")}
              {f !== "ALL" && counts[f] ? ` · ${counts[f]}` : ""}
            </button>
          ))}
        </div>

        {loading && all.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border/60 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Loading escalations…
          </div>
        ) : (
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-2">
              <TableToolbar
                search={search}
                onSearchChange={setSearch}
                placeholder="Search service, escalation, decision, anomaly..."
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
                emptyMessage="No escalations match this filter."
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

            {/* Detail */}
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
                      <StatusBadge status={selected.status} />
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
                        <dt className="text-muted-foreground">Anomaly</dt>
                        <dd className="truncate font-mono text-[10px]">
                          {selected.anomaly_id}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-2">
                        <dt className="text-muted-foreground">Created</dt>
                        <dd className="font-mono text-[10px]">
                          {formatStamp(selected.created_at)}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div className="rounded-xl border border-border/60 p-3">
                    <p className="mb-2 flex items-center gap-1 text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                      <Timer className="size-3" />
                      Delivery plan
                    </p>
                    <ol className="space-y-2">
                      {ATTEMPT_PLAN.map((plan) => {
                        const sent = selectedAttempts.find(
                          (n) => n.attempt === plan.attempt,
                        );
                        return (
                          <li key={plan.attempt} className="flex gap-2">
                            <span
                              className={cn(
                                "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border text-[8px] font-mono",
                                sent?.sent
                                  ? "border-status-healthy/60 bg-status-healthy/15 text-status-healthy"
                                  : sent
                                    ? "border-status-critical/60 bg-status-critical/15 text-status-critical"
                                    : "border-border text-muted-foreground",
                              )}
                            >
                              {sent?.sent ? <Check className="size-2.5" /> : plan.attempt}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-baseline justify-between gap-2">
                                <span className="text-[11px] font-medium">
                                  {plan.template}{" "}
                                  <span className="font-mono text-[9px] text-muted-foreground">
                                    {plan.at}
                                  </span>
                                </span>
                                <span className="shrink-0 font-mono text-[9px] text-muted-foreground">
                                  {sent?.sent_at ? formatClock(sent.sent_at) : "—"}
                                </span>
                              </div>
                              <p className="truncate text-[10px] text-muted-foreground">
                                {sent?.subject ?? "not sent yet"}
                              </p>
                              {sent?.error && (
                                <p className="text-[10px] text-status-critical">
                                  {sent.error}
                                </p>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ol>
                  </div>

                  {selectedResponse && (
                    <div className="rounded-xl border border-status-healthy/40 bg-status-healthy/5 p-3">
                      <p className="text-[10px] font-medium tracking-wider text-status-healthy uppercase">
                        Operator response
                      </p>
                      <p className="mt-1 text-xs">
                        <span className="font-mono font-semibold">
                          {selectedResponse.decision}
                        </span>{" "}
                        by {selectedResponse.by ?? "unknown"}
                      </p>
                      <p className="font-mono text-[10px] text-muted-foreground">
                        {selectedResponse.at ? formatStamp(selectedResponse.at) : "—"}
                      </p>
                      {selectedResponse.note && (
                        <p className="mt-1 text-[11px]">{selectedResponse.note}</p>
                      )}
                      {selectedResponse.execution && (
                        <div className="mt-2 rounded-md border border-border/60 bg-background/70 p-2">
                          <p className="text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
                            Action performed
                          </p>
                          <p className="mt-0.5 font-mono text-[11px]">
                            <span className="font-semibold">
                              {selectedResponse.execution.status ?? "—"}
                            </span>
                            {selectedResponse.execution.action
                              ? ` · ${selectedResponse.execution.action}`
                              : ""}
                          </p>
                          {selectedResponse.execution.message && (
                            <p className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
                              {selectedResponse.execution.message}
                            </p>
                          )}
                          {selectedResponse.execution.executed_at && (
                            <p className="mt-0.5 font-mono text-[9px] text-muted-foreground">
                              {formatStamp(selectedResponse.execution.executed_at)}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {selected.failure_report && (
                    <div className="rounded-xl border border-status-critical/40 bg-status-critical/5 p-3 text-[11px]">
                      <p className="mb-1 text-[10px] font-medium tracking-wider text-status-critical uppercase">
                        Manual intervention required
                      </p>
                      {selected.failure_report}
                    </div>
                  )}

                  {!terminal(selected.status) && (
                    <div className="rounded-xl border border-border/60 p-3">
                      <p className="mb-2 flex items-center gap-1 text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                        <BellRing className="size-3" />
                        Decide
                      </p>
                      <Input
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Note recorded in the audit trail"
                        className="mb-2 h-7 text-xs"
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="h-7 flex-1 bg-status-healthy text-white hover:bg-status-healthy/90"
                          disabled={busy === selected.id}
                          onClick={() => ack(selected, "APPROVED")}
                        >
                          {busy === selected.id ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : (
                            <Check className="size-3.5" />
                          )}
                          Approve &amp; run
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 flex-1"
                          disabled={busy === selected.id}
                          onClick={() => ack(selected, "REJECTED")}
                        >
                          <X className="size-3.5" />
                          Reject
                        </Button>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="mt-2 h-7 w-full text-[10px] text-muted-foreground"
                        disabled={busy === selected.id}
                        onClick={() => fire(selected)}
                        title="Debug: force the next attempt to fire now instead of waiting"
                      >
                        <Send className="size-3" />
                        Fire next attempt now
                      </Button>
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

function escalationSortValue(row: ApiEscalationRow, key: string): string | number | null {
  switch (key) {
    case "service":
      return row.service_id;
    case "status":
      return row.status;
    case "attempt":
      return row.attempt;
    case "next_attempt_at":
      return row.next_attempt_at ?? "";
    case "created_at":
      return row.created_at;
    default:
      return null;
  }
}
