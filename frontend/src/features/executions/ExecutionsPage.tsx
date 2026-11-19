// frontend\src\features\executions\ExecutionsPage.tsx
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Ban,
  Cpu,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePoll } from "@/hooks/usePoll";
import {
  fetchDecisions,
  fetchExecutions,
  type ApiDecision,
  type ApiExecutionRow,
} from "@/lib/api";
import { formatClock, ago } from "@/features/decisions/lib/format";

const STATUS_STYLE: Record<string, string> = {
  SUCCESS: "bg-status-healthy/12 text-status-healthy border-status-healthy/40",
  FAILED: "bg-status-critical/12 text-status-critical border-status-critical/40",
  DRY_RUN: "bg-status-shadow/12 text-status-shadow border-status-shadow/40",
  NOT_IMPLEMENTED: "bg-status-warn/12 text-status-warn border-status-warn/40",
  SKIPPED: "bg-muted text-muted-foreground border-border",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "rounded-full border px-1.5 py-px font-mono text-[9px] font-medium uppercase",
        STATUS_STYLE[status] ?? "border-border bg-muted text-muted-foreground",
      )}
    >
      {status}
    </span>
  );
}

/**
 * Execution log (stage 7) plus the guardrail evidence trail (stage 6).
 *
 * The executor is intentionally visible here: when the engine runs with
 * `KUBERNETES_DRY_RUN=1` the Noop executor still writes a row with status
 * NOT_IMPLEMENTED, so the log proves the decision reached execution even when
 * no cluster was touched. A guardrail block is the opposite: a decision that
 * never produced an execution row at all.
 */
export function ExecutionsPage() {
  const executions = usePoll<ApiExecutionRow[]>(() => fetchExecutions(200), {
    pollMs: 20000,
    key: "executions",
  });
  const decisions = usePoll<ApiDecision[]>(() => fetchDecisions(200), {
    pollMs: 20000,
    key: "executions-decisions",
  });

  const rows = executions.data ?? [];
  const allDecisions = decisions.data ?? [];

  const counts = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const row of rows) acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, [rows]);

  const guardrailBlocks = useMemo(
    () =>
      allDecisions.filter(
        (d) =>
          d.policy?.outcome === "BLOCK" && /guardrail/i.test(d.policy?.reason ?? ""),
      ),
    [allDecisions],
  );

  const dryRun = (counts.NOT_IMPLEMENTED ?? 0) > 0 && (counts.SUCCESS ?? 0) === 0;

  const perService = useMemo(() => {
    const acc = new Map<string, { total: number; last: string }>();
    for (const row of rows) {
      const current = acc.get(row.service_id);
      if (!current) {
        acc.set(row.service_id, { total: 1, last: row.executed_at });
      } else {
        current.total += 1;
        if (row.executed_at > current.last) current.last = row.executed_at;
      }
    }
    return [...acc.entries()].sort((a, b) => b[1].total - a[1].total);
  }, [rows]);

  const error = executions.error ?? decisions.error;
  const loading = executions.loading && rows.length === 0;

  return (
    <AppShell pageTitle="Executions">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Execution &amp; guardrails</h2>
            <p className="text-sm text-muted-foreground">
              What the executor actually did, and every action the safety
              guardrails refused to send. Both are written by the pipeline at
              runtime — nothing here is simulated by the UI.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            className="h-7"
            onClick={() => {
              executions.refresh();
              decisions.refresh();
            }}
            disabled={executions.loading}
          >
            <RefreshCw
              className={cn("size-3.5", executions.loading && "animate-spin")}
            />
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
          {[
            { label: "Executions", value: rows.length, icon: Cpu },
            { label: "Succeeded", value: counts.SUCCESS ?? 0, icon: ShieldCheck },
            { label: "Failed", value: counts.FAILED ?? 0, icon: AlertTriangle },
            {
              label: "Dry-run / no-op",
              value: (counts.NOT_IMPLEMENTED ?? 0) + (counts.DRY_RUN ?? 0),
              icon: Ban,
            },
            {
              label: "Guardrail blocks",
              value: guardrailBlocks.length,
              icon: ShieldCheck,
            },
          ].map((tile) => (
            <div
              key={tile.label}
              className="flex items-start gap-2 rounded-lg border border-border/60 px-3 py-2"
            >
              <tile.icon className="mt-0.5 size-3.5 text-muted-foreground" />
              <div>
                <p className="text-[9px] font-medium tracking-wider text-muted-foreground uppercase">
                  {tile.label}
                </p>
                <p className="font-mono text-lg leading-none">{tile.value}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-border/60 px-3 py-2 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">Executor: </span>
          {dryRun
            ? "Noop (KUBERNETES_DRY_RUN=1) — every action is recorded as NOT_IMPLEMENTED, which means the decision reached execution but no cluster call was made."
            : rows.length > 0
              ? "Kubernetes client is issuing real calls — statuses below come from the API server, not a dry run."
              : "No executions recorded yet, so the executor mode cannot be inferred. See services/decision-engine/.env.example for KUBERNETES_* settings."}
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-lg border border-status-critical/40 bg-status-critical/5 p-2.5 text-[11px]">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-status-critical" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border/60 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Loading execution log…
          </div>
        ) : (
          <div className="grid gap-3 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
            <div className="overflow-hidden rounded-xl border border-border/60">
              <div className="flex items-center justify-between border-b border-border/40 px-3 py-2">
                <p className="text-xs font-semibold">Execution log</p>
                <span className="font-mono text-[10px] text-muted-foreground">
                  {rows.length} rows
                </span>
              </div>
              {rows.length === 0 ? (
                <p className="px-3 py-8 text-center text-xs text-muted-foreground">
                  No executions yet. Only an AUTO_EXECUTE decision reaches the
                  executor — see the leaf-service scenario in
                  validation/README.md.
                </p>
              ) : (
                <div className="max-h-[32rem] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-muted/60 text-[9px] tracking-wider text-muted-foreground uppercase backdrop-blur">
                      <tr>
                        <th className="px-2.5 py-1.5 text-left">Time</th>
                        <th className="px-2.5 py-1.5 text-left">Service</th>
                        <th className="px-2.5 py-1.5 text-left">Action</th>
                        <th className="px-2.5 py-1.5 text-left">Status</th>
                        <th className="px-2.5 py-1.5 text-left">Message</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr
                          key={`${row.id}-${row.decision_id}`}
                          className="border-t border-border/50 align-top"
                        >
                          <td className="px-2.5 py-1.5 whitespace-nowrap font-mono text-[10px] text-muted-foreground">
                            {formatClock(row.executed_at)}
                          </td>
                          <td className="px-2.5 py-1.5">
                            <div className="font-medium">{row.service_id}</div>
                            <Link
                              to={`/decisions/${encodeURIComponent(row.decision_id)}`}
                              className="font-mono text-[9px] text-status-warn hover:underline"
                            >
                              run →
                            </Link>
                          </td>
                          <td className="px-2.5 py-1.5 font-mono text-[10px]">
                            {row.action}
                          </td>
                          <td className="px-2.5 py-1.5">
                            <StatusBadge status={row.status} />
                          </td>
                          <td
                            className="max-w-[18rem] px-2.5 py-1.5 text-[10px] text-muted-foreground"
                            title={row.message ?? ""}
                          >
                            <span className="line-clamp-2">{row.message ?? "—"}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="space-y-3">
              <div className="rounded-xl border border-border/60">
                <div className="flex items-center justify-between border-b border-border/40 px-3 py-2">
                  <p className="text-xs font-semibold">Guardrail blocks</p>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {guardrailBlocks.length}
                  </span>
                </div>
                {guardrailBlocks.length === 0 ? (
                  <p className="px-3 py-6 text-center text-[11px] text-muted-foreground">
                    No decision has been vetoed by the guardrails yet. Re-trigger
                    the same scenario within the cooldown window to produce one.
                  </p>
                ) : (
                  <ul className="max-h-56 divide-y divide-border/40 overflow-y-auto">
                    {guardrailBlocks.map((d) => (
                      <li key={d.decision_id} className="px-3 py-2">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-[11px] font-medium">
                            {d.service_id} · {d.action}
                          </span>
                          <span className="shrink-0 font-mono text-[9px] text-muted-foreground">
                            {ago(d.created_at)}
                          </span>
                        </div>
                        <p className="mt-0.5 text-[10px] text-status-critical">
                          {d.policy?.reason ?? "blocked"}
                        </p>
                        <Link
                          to={`/decisions/${encodeURIComponent(d.decision_id)}`}
                          className="font-mono text-[9px] text-status-warn hover:underline"
                        >
                          open run →
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="rounded-xl border border-border/60">
                <div className="border-b border-border/40 px-3 py-2">
                  <p className="text-xs font-semibold">Actions per service</p>
                </div>
                {perService.length === 0 ? (
                  <p className="px-3 py-6 text-center text-[11px] text-muted-foreground">
                    Nothing executed yet.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/40">
                    {perService.slice(0, 8).map(([service, info]) => (
                      <li
                        key={service}
                        className="flex items-center justify-between gap-2 px-3 py-1.5 text-[11px]"
                      >
                        <span className="truncate">{service}</span>
                        <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                          {info.total} · last {formatClock(info.last)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="border-t border-border/40 px-3 py-2 text-[10px] text-muted-foreground">
                  Rate limiting is per-rule (<span className="font-mono">max_per_hour</span>,
                  default 3) and enforced by the guardrail counter against{" "}
                  <span className="font-mono">action_history</span>.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
