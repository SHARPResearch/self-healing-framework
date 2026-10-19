import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useLiveStore } from "@/shared/store/liveStore";
import { ACTION_LABEL, ACTION_TONE, TRIGGER_LABEL, VERDICT_LABEL, pct } from "../lib/format";
import { Pill } from "./Pill";

/**
 * The audit trail of closed quarantines and operator actions. Routine "resume" outcomes (a check
 * that found nothing) are left out unless asked for, so promotions, holds and questions stand out.
 */
export function DecisionLog({ includeResume = false }: { includeResume?: boolean }) {
  const decisions = useLiveStore((s) => s.decisions);
  const services = useLiveStore((s) => s.services);
  const rows = (includeResume ? decisions : decisions.filter((d) => d.action !== "resume")).slice(0, 60);

  return (
    <div className="rounded-xl border border-border/60 p-4">
      <h3 className="text-base font-semibold">Decision audit trail</h3>
      <p className="mb-3 text-sm text-muted-foreground">
        Every verdict with the evidence it rested on. Persisted to TimescaleDB (lifecycle_decisions).
      </p>
      <ScrollArea className="h-80">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Service</TableHead>
              <TableHead>Trigger</TableHead>
              <TableHead>Verdict</TableHead>
              <TableHead>Action</TableHead>
              <TableHead className="text-right">Serving alarms</TableHead>
              <TableHead className="text-right">Challenger</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-xs text-muted-foreground">
                  No decisions yet.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((d, i) => (
                <TableRow key={`${d.serviceId}-${d.step}-${i}`} title={d.reason}>
                  <TableCell className="text-xs">
                    {services[d.serviceId]?.displayName ?? d.serviceId}
                    <div className="font-mono text-[10px] text-muted-foreground">step {d.step}</div>
                  </TableCell>
                  <TableCell className="text-xs">{TRIGGER_LABEL[d.trigger] ?? d.trigger}</TableCell>
                  <TableCell className="text-xs">{VERDICT_LABEL[d.verdict] ?? d.verdict}</TableCell>
                  <TableCell>
                    <Pill tone={ACTION_TONE[d.action] ?? "neutral"}>
                      {ACTION_LABEL[d.action] ?? d.action}
                      {d.queryId && d.action !== "ask" ? " (operator)" : ""}
                    </Pill>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {pct(d.evidence.champion_tail_alarm_rate)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {pct(d.evidence.challenger_tail_alarm_rate)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  );
}
