// frontend\src\features\decisions\DecisionRunPage.tsx
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Loader2, RefreshCw } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { Button } from "@/components/ui/button";
import { fetchDecision, type ApiDecision } from "@/lib/api";
import { formatStamp } from "./lib/format";
import { DecisionFlow } from "./components/DecisionFlow";
import { cn } from "@/lib/utils";

const SEVERITY_CLASS: Record<string, string> = {
  LOW: "bg-status-healthy/10 text-status-healthy border-status-healthy/30",
  MEDIUM: "bg-status-degrade/10 text-status-degrade border-status-degrade/30",
  HIGH: "bg-status-escalated/10 text-status-escalated border-status-escalated/30",
  CRITICAL: "bg-status-critical/10 text-status-critical border-status-critical/30",
};

/**
 * Full-page view of one decision run: every stage from anomaly to execution
 * (or escalation / shadow / block) with its timing, plus the notifications
 * the engine raised. Deep-linkable at /decisions/:decisionId.
 */
export function DecisionRunPage() {
  const { decisionId } = useParams<{ decisionId: string }>();
  const [decision, setDecision] = useState<ApiDecision | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const load = useCallback(async () => {
    if (!decisionId) return;
    setLoading(true);
    try {
      const result = await fetchDecision(decisionId);
      setDecision(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [decisionId]);

  useEffect(() => {
    void load();
  }, [load, nonce]);

  const unvalidated =
    !decision?.policy?.outcome || decision.policy.outcome === "UNVALIDATED";

  return (
    <AppShell pageTitle="Decision run">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              to="/decisions"
              className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="size-3" />
              All decisions
            </Link>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold">
                {decision?.service_id ?? "Decision run"}
              </h2>
              {decision && (
                <span
                  className={cn(
                    "rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase",
                    SEVERITY_CLASS[decision.severity?.label ?? ""] ?? "",
                  )}
                >
                  {decision.severity?.label ?? "—"}
                </span>
              )}
              {decision && (
                <span className="rounded-full bg-status-warn/10 px-2 py-0.5 font-mono text-[10px] font-medium text-status-warn">
                  {decision.action}
                </span>
              )}
            </div>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground">
              {decisionId}
              {decision && ` · anomaly ${decision.anomaly_id}`}
              {decision && ` · ${formatStamp(decision.created_at)}`}
            </p>
          </div>

          <Button
            size="sm"
            variant="outline"
            className="h-7"
            onClick={() => setNonce((n) => n + 1)}
            disabled={loading}
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-status-critical/40 bg-status-critical/5 p-3 text-xs">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-critical" />
            <span>{error}</span>
          </div>
        )}

        {loading && !decision ? (
          <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-border/60 text-xs text-muted-foreground">
            <Loader2 className="mr-2 size-4 animate-spin" />
            Loading decision…
          </div>
        ) : decision ? (
          <>
            {unvalidated && (
              <p className="rounded-xl border border-status-degrade/40 bg-status-degrade/5 px-3 py-2 text-[11px] text-status-degrade">
                This row was persisted before the validation layer ran. The graph
                marks validation as the step in progress and leaves the routing
                branches untaken — that is the real state of the record, not a
                rendering gap.
              </p>
            )}
            <DecisionFlow
              decision={decision}
              pollMs={unvalidated ? 5000 : 0}
            />
          </>
        ) : (
          <p className="rounded-xl border border-dashed border-border/60 p-6 text-center text-xs text-muted-foreground">
            No decision with that id.
          </p>
        )}
      </div>
    </AppShell>
  );
}
