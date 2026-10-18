import { ArrowRight } from "lucide-react";
import { Pill } from "./Pill";
import type { Tone } from "../lib/format";

const STEPS: { title: string; body: string }[] = [
  { title: "Trigger", body: "ADWIN drift on the score, a deployment event, or a scheduled check" },
  { title: "Quarantine", body: "One day of evidence; the champion keeps serving, nothing is learned" },
  { title: "Attribute", body: "Champion vs re-baselined vs retrained challenger, against per service null floors" },
  { title: "Act", body: "A versioned, audited transition, or a question to the operator" },
];

const MAPPING: { verdict: string; action: string; tone: Tone }[] = [
  { verdict: "Concept drift", action: "promote", tone: "good" },
  { verdict: "Model decay", action: "roll back", tone: "warn" },
  { verdict: "Incident", action: "hold", tone: "bad" },
  { verdict: "No change", action: "resume", tone: "neutral" },
  { verdict: "Ambiguous", action: "ask operator", tone: "info" },
];

/** One line legend of CADAL for the audience: what happens between a shift and a model change. */
export function CadalExplainer() {
  return (
    <div className="rounded-xl border border-border/60 p-4">
      <div className="grid gap-3 md:grid-cols-4">
        {STEPS.map((s, i) => (
          <div key={s.title} className="flex items-start gap-2">
            <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[11px]">
              {i + 1}
            </span>
            <div className="min-w-0">
              <p className="flex items-center gap-1 text-sm font-medium">
                {s.title}
                {i < STEPS.length - 1 && <ArrowRight className="hidden size-3 text-muted-foreground md:inline" />}
              </p>
              <p className="text-xs text-muted-foreground">{s.body}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-2 border-t border-border/60 pt-3">
        {MAPPING.map((m) => (
          <Pill key={m.verdict} tone={m.tone}>
            {m.verdict} → {m.action}
          </Pill>
        ))}
      </div>
    </div>
  );
}
