import { useState } from "react";
import { HelpCircle, Loader2, ShieldAlert, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { refreshLive } from "@/hooks/useLiveConnection";
import { useLiveStore } from "@/shared/store/liveStore";
import type { OperatorQuery, QueryAnswer } from "../types";
import { explainQuery } from "../lib/format";

/**
 * CADAL-HITL: the lifecycle could not attribute a persistent shift without labels, so it keeps the
 * champion serving, parks the validated challenger, and asks. The answer is attribution evidence:
 * "new normal" promotes the parked challenger (audited with this query id), "incident" keeps
 * the champion and pauses asking.
 */
export function OperatorQueryCard({ query }: { query: OperatorQuery }) {
  const operator = useLiveStore((s) => s.operator);
  const eps = useLiveStore((s) => s.health?.eventsPerSec ?? 60);
  const step = useLiveStore((s) => s.scores[query.serviceId]?.at(-1)?.step ?? query.currentStep);
  const [busy, setBusy] = useState<QueryAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const remaining = Math.max(0, query.expiresStep - step);
  const seconds = Math.round(remaining / Math.max(eps, 1));

  const answer = async (value: QueryAnswer) => {
    setBusy(value);
    setError(null);
    try {
      await api.answer(query.queryId, value, operator || "operator");
      await refreshLive();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-xl border border-status-warn/50 bg-status-warn/5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <HelpCircle className="mt-0.5 size-5 shrink-0 text-status-warn" />
          <div>
            <p className="text-sm font-semibold">
              {query.serviceName}: new normal, or incident?
            </p>
            <p className="font-mono text-xs text-muted-foreground">
              {query.queryId} · falls back to hold in {Math.floor(seconds / 60)}:
              {String(seconds % 60).padStart(2, "0")}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" disabled={busy !== null} onClick={() => answer("new_normal")}>
            {busy === "new_normal" ? <Loader2 className="animate-spin" /> : <Sparkles />}
            New normal
          </Button>
          <Button size="sm" variant="outline" disabled={busy !== null} onClick={() => answer("incident")}>
            {busy === "incident" ? <Loader2 className="animate-spin" /> : <ShieldAlert />}
            Incident
          </Button>
        </div>
      </div>
      <ul className="mt-3 space-y-1 pl-8 text-xs text-muted-foreground">
        {explainQuery(query).map((line) => (
          <li key={line} className="list-disc">
            {line}
          </li>
        ))}
      </ul>
      {error && <p className="mt-2 pl-8 text-xs text-status-critical">{error}</p>}
    </div>
  );
}
