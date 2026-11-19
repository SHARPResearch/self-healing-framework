// frontend\src\features\notifications\NotificationsPage.tsx
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BellOff, Loader2, RefreshCw, Send } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePoll } from "@/hooks/usePoll";
import { fetchNotifications, type ApiNotificationEntry } from "@/lib/api";
import { formatStamp, ago } from "@/features/decisions/lib/format";

/**
 * Every email the decision engine attempted to send — the `notifications`
 * table, which `app/notifications/emailer.py` writes on every delivery
 * attempt whether or not the SMTP send succeeded. This is the audit trail
 * behind "did anyone get told?", so it reads the live API rather than the
 * in-app feed's mock store.
 */

const STATUS_STYLE: Record<string, string> = {
  SENT: "bg-status-healthy/12 text-status-healthy border-status-healthy/40",
  FAILED: "bg-status-critical/12 text-status-critical border-status-critical/40",
  SKIPPED: "bg-status-degrade/12 text-status-degrade border-status-degrade/40",
  PENDING: "bg-status-warn/12 text-status-warn border-status-warn/40",
};

const KIND_LABEL: Record<string, string> = {
  ANOMALY_DETECTED: "Anomaly detected",
  DECISION_MADE: "Recovery decision",
  ESCALATION: "Escalation",
};

const FILTERS = ["all", "SENT", "FAILED", "SKIPPED"] as const;
type Filter = (typeof FILTERS)[number];

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

export function NotificationsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const { data, loading, error, refresh } = usePoll<ApiNotificationEntry[]>(
    () => fetchNotifications(200),
    { pollMs: 20000, key: "notifications" },
  );

  const all = data ?? [];

  const counts = useMemo(() => {
    const acc: Record<string, number> = { SENT: 0, FAILED: 0, SKIPPED: 0, PENDING: 0 };
    for (const row of all) acc[row.status] = (acc[row.status] ?? 0) + 1;
    return acc;
  }, [all]);

  const visible = filter === "all" ? all : all.filter((n) => n.status === filter);

  return (
    <AppShell pageTitle="Notifications">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Delivery log</h2>
            <p className="text-sm text-muted-foreground">
              Every email the engine attempted, including the ones that never
              left: <span className="font-mono">FAILED</span> means SMTP rejected
              or dropped the send, <span className="font-mono">SKIPPED</span>{" "}
              means the mailer ran in dry-run mode.
            </p>
          </div>
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

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(
            [
              ["SENT", "Delivered"],
              ["FAILED", "Rejected by SMTP"],
              ["SKIPPED", "Dry-run"],
              ["PENDING", "Queued"],
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

        <div className="flex flex-wrap gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={cn(
                "rounded-full border px-2.5 py-1 text-[10px] font-medium",
                filter === f
                  ? "border-foreground/30 bg-accent text-accent-foreground"
                  : "border-border/60 text-muted-foreground hover:text-foreground",
              )}
            >
              {f === "all" ? "All" : f}
              {f !== "all" && counts[f] ? ` · ${counts[f]}` : ""}
            </button>
          ))}
        </div>

        {error && (
          <p className="rounded-lg border border-status-critical/40 bg-status-critical/5 p-2.5 text-[11px]">
            {error}
          </p>
        )}

        {loading && all.length === 0 ? (
          <div className="flex h-40 items-center justify-center rounded-xl border border-dashed border-border/60 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Loading delivery log…
          </div>
        ) : visible.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border py-16 text-center">
            <BellOff className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {all.length === 0
                ? "No delivery attempts yet. Trigger a scenario on /anomalies to make the engine send one."
                : "Nothing here for this filter"}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {visible.map((n) => (
              <div
                key={n.id}
                className="rounded-xl border border-border/60 px-3 py-2.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="rounded bg-muted px-1.5 py-px text-[9px] font-medium tracking-wide text-muted-foreground uppercase">
                        {KIND_LABEL[n.kind] ?? n.kind}
                      </span>
                      {n.service_id && (
                        <span className="text-[11px] font-medium">
                          {n.service_id}
                        </span>
                      )}
                      <StatusBadge status={n.status} />
                    </div>
                    <p className="mt-1 text-[12px] leading-snug font-medium">
                      {n.subject}
                    </p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Send className="size-2.5" />
                        {n.recipient}
                      </span>
                      {n.anomaly_id && (
                        <span className="font-mono">{n.anomaly_id}</span>
                      )}
                      {n.decision_id && (
                        <Link
                          to={`/decisions/${encodeURIComponent(n.decision_id)}`}
                          className="font-mono text-status-warn hover:underline"
                        >
                          open run →
                        </Link>
                      )}
                    </p>
                    {n.error && (
                      <p className="mt-1 rounded bg-status-critical/5 px-1.5 py-1 text-[10px] leading-snug text-status-critical">
                        {n.error}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="font-mono text-[10px] text-muted-foreground">
                      {ago(n.created_at)}
                    </p>
                    <p className="font-mono text-[9px] text-muted-foreground/70">
                      {formatStamp(n.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
