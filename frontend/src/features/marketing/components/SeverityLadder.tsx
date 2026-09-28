import type { Severity } from "@/shared/types";
import { LADDER } from "../data/marketingContent";
import { Reveal } from "./Reveal";

/** Same tokens the real app uses, so the marketing page is not a reskin. */
const BAR: Record<Severity, string> = {
  watch: "bg-status-watch",
  warn: "bg-status-warn",
  degrade: "bg-status-degrade",
  critical: "bg-status-critical",
};

const TEXT: Record<Severity, string> = {
  watch: "text-status-watch",
  warn: "text-status-warn",
  degrade: "text-status-degrade",
  critical: "text-status-critical",
};

export function SeverityLadder() {
  return (
    <section id="remediation" className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">
          Graduated remediation
        </p>
        <h2 className="mt-3 max-w-2xl text-3xl font-medium tracking-display text-foreground sm:text-4xl">
          It does not just restart everything
        </h2>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-foreground/60">
          The response scales with the anomaly score. A mild anomaly gets a warmed up replica, not a
          pod kill. Only a genuinely critical score triggers the full drain, restart and rollback.
        </p>
      </Reveal>

      <div className="mt-14 space-y-3">
        {LADDER.map((rung, i) => (
          <Reveal key={rung.severity} delay={i * 0.08}>
            <div className="flex flex-col gap-3 rounded-brand-lg border border-foreground/10 bg-foreground/[0.03] p-5 sm:flex-row sm:items-center sm:gap-6">
              {/* Severity colours (BAR/TEXT below) are a separate semantic
                  system from brand-primary and are exempt from the sparse
                  green rule -- unchanged here on purpose. */}
              <div className={`h-1 w-full rounded-full sm:h-10 sm:w-1 ${BAR[rung.severity]}`} />
              <div className="w-full sm:w-40">
                <p className={`text-sm font-semibold capitalize ${TEXT[rung.severity]}`}>
                  {rung.severity}
                </p>
                <p className="font-mono text-xs text-foreground/40">{rung.range}</p>
              </div>
              <p className="flex-1 text-sm text-foreground/70">{rung.action}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
