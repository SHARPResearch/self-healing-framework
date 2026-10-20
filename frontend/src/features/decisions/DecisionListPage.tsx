import { useState } from "react";
import { AppShell } from "@/shared/layout/AppShell";
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

        <div className="overflow-hidden rounded-xl border border-border/60">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">Service</th>
                <th className="px-3 py-2 text-left">Action</th>
                <th className="px-3 py-2 text-left">Rule</th>
                <th className="px-3 py-2 text-left">Severity</th>
                <th className="px-3 py-2 text-right">Confidence</th>
                <th className="px-3 py-2 text-left">Policy</th>
                <th className="px-3 py-2 text-left">Created</th>
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
              {!loading && !error && items.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-8 text-center text-muted-foreground"
                  >
                    No decisions yet. Trigger a scenario to see decisions
                    appear.
                  </td>
                </tr>
              )}
              {items.map((d) => (
                <tr
                  key={d.decision_id}
                  onClick={() => setOpen(d)}
                  className="cursor-pointer border-t border-border/60 transition-colors hover:bg-accent/50"
                >
                  <td className="px-3 py-2">
                    <div className="font-medium">{d.service_id}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {d.anomaly_id}
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{d.action}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {d.rule_id ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase ${
                        SEVERITY_STYLES[d.severity.label] ?? ""
                      }`}
                    >
                      {d.severity.label}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
                    {(d.confidence.final * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-medium ${
                        OUTCOME_STYLES[d.policy.outcome ?? "UNVALIDATED"] ?? ""
                      }`}
                    >
                      {d.policy.outcome ?? "UNVALIDATED"}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                    {new Date(d.created_at).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <DecisionDetailModal decision={open} onClose={() => setOpen(null)} />
    </AppShell>
  );
}
