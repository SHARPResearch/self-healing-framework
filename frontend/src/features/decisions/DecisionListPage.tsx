import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AppShell } from "@/shared/layout/AppShell";
import { ListTable, Pagination, TableToolbar, useListControls } from "@/shared/components/ListTable";
import type { ListColumn, SortState } from "@/shared/components/ListTable";
import { DecisionDetailModal } from "./components/DecisionDetailModal";
import { useDecisions } from "./data/useDecisions";
import type { ApiDecision } from "@/lib/api";

const SEVERITY_STYLES: Record<string, string> = {
  LOW: "bg-green-500/10 text-green-600 border-green-500/30",
  MEDIUM: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  HIGH: "bg-orange-500/10 text-orange-600 border-orange-500/30",
  CRITICAL: "bg-red-500/10 text-red-600 border-red-500/30",
};

const OUTCOME_STYLES: Record<string, string> = {
  AUTO_EXECUTE: "bg-green-500/10 text-green-600",
  SHADOW_MODE: "bg-blue-500/10 text-blue-600",
  HUMAN_LOOP: "bg-amber-500/10 text-amber-600",
  BLOCK: "bg-red-500/10 text-red-600",
  NO_RULE_MATCHED: "bg-zinc-500/10 text-zinc-600",
  UNVALIDATED: "bg-zinc-500/10 text-zinc-600",
};

export function DecisionListPage() {
  const { items, loading, error } = useDecisions(5000);
  const [open, setOpen] = useState<ApiDecision | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sort, setSort] = useState<SortState | null>({
    key: "created_at",
    direction: "desc",
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  useEffect(() => {
    const focus = searchParams.get("focus");
    if (!focus || items.length === 0) return;
    const match = items.find((d) => d.decision_id === focus);
    if (match) {
      setOpen(match);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, items, setSearchParams]);

  useEffect(() => setPage(1), [search, dateFrom, dateTo]);

  const closeModal = () => {
    setOpen(null);
    if (searchParams.get("focus")) setSearchParams({}, { replace: true });
  };

  const table = useListControls({
    rows: items,
    search,
    searchValues: (row) => [
      row.decision_id,
      row.anomaly_id,
      row.service_id,
      row.action,
      row.rule_id ?? "",
      row.severity.label,
      row.policy.outcome ?? "",
      row.policy.reason ?? "",
    ],
    dateField: (row) => row.created_at,
    dateFrom,
    dateTo,
    sort,
    sortValue: (row, key) => decisionSortValue(row, key),
    page,
    pageSize,
  });

  const columns = useMemo<ListColumn<ApiDecision>[]>(
    () => [
      {
        key: "service",
        header: "Service",
        sortValue: (row) => row.service_id,
        render: (row) => (
          <>
            <div className="font-medium">{row.service_id}</div>
            <div className="font-mono text-[10px] text-muted-foreground">
              {row.anomaly_id}
            </div>
          </>
        ),
      },
      {
        key: "action",
        header: "Action",
        sortValue: (row) => row.action,
        className: "font-mono text-xs",
        render: (row) => row.action,
      },
      {
        key: "rule",
        header: "Rule",
        sortValue: (row) => row.rule_id ?? "",
        className: "font-mono text-xs text-muted-foreground",
        render: (row) => row.rule_id ?? "—",
      },
      {
        key: "severity",
        header: "Severity",
        sortValue: (row) => row.severity.label,
        render: (row) => (
          <span
            className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase ${
              SEVERITY_STYLES[row.severity.label] ?? ""
            }`}
          >
            {row.severity.label}
          </span>
        ),
      },
      {
        key: "confidence",
        header: "Confidence",
        sortValue: (row) => row.confidence.final,
        className: "text-right font-mono text-xs",
        render: (row) => `${(row.confidence.final * 100).toFixed(1)}%`,
      },
      {
        key: "policy",
        header: "Policy",
        sortValue: (row) => row.policy.outcome ?? "",
        render: (row) => (
          <span
            className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-medium ${
              OUTCOME_STYLES[row.policy.outcome ?? "UNVALIDATED"] ?? ""
            }`}
          >
            {row.policy.outcome ?? "UNVALIDATED"}
          </span>
        ),
      },
      {
        key: "created_at",
        header: "Created",
        sortValue: (row) => row.created_at,
        className: "font-mono text-xs text-muted-foreground",
        render: (row) => new Date(row.created_at).toLocaleString(),
      },
    ],
    [],
  );

  return (
    <AppShell pageTitle="Decisions">
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-semibold">Decision log</h2>
          <p className="text-sm text-muted-foreground">
            Every rule-based decision the engine has made. Click a row to see
            the full reasoning flow.
          </p>
        </div>

        <TableToolbar
          search={search}
          onSearchChange={setSearch}
          placeholder="Search decision, anomaly, service, rule, policy..."
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />
        <ListTable
          columns={columns}
          rows={table.visibleRows}
          rowKey={(row) => row.decision_id}
          loading={loading}
          error={error}
          emptyMessage="No decisions yet. Trigger a scenario to see decisions appear."
          sort={sort}
          onSortChange={setSort}
          onRowClick={setOpen}
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

      <DecisionDetailModal decision={open} onClose={closeModal} />
    </AppShell>
  );
}

function decisionSortValue(row: ApiDecision, key: string): string | number | null {
  switch (key) {
    case "service":
      return row.service_id;
    case "action":
      return row.action;
    case "rule":
      return row.rule_id ?? "";
    case "severity":
      return row.severity.label;
    case "confidence":
      return row.confidence.final;
    case "policy":
      return row.policy.outcome ?? "";
    case "created_at":
      return row.created_at;
    default:
      return null;
  }
}
