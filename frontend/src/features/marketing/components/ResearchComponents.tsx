import { cn } from "@/lib/utils";
import { RESEARCH_COMPONENTS, type ResearchComponent } from "../data/marketingContent";
import { Reveal } from "./Reveal";

/** "Complete" is exempt from the sparse green rule -- it's a genuine progress
 *  status (this project's honest self-reporting device), not brand color. */
const STATUS_CLASS: Record<ResearchComponent["status"], string> = {
  Complete: "bg-status-healthy/15 text-status-healthy",
  "In progress": "bg-status-warn/15 text-status-warn",
  Planned: "bg-foreground/10 text-foreground/50",
};

export function ResearchComponents() {
  return (
    <section id="research" className="border-y border-foreground/10 bg-foreground/[0.02]">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">
            Research components
          </p>
          <h2 className="mt-3 max-w-2xl text-3xl font-medium tracking-display text-foreground sm:text-4xl">
            Five parts, built and evaluated separately
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-foreground/60">
            SHARP is a final year research project, and this is an honest view of where each piece
            actually is. Component 1 is complete and benchmarked; the rest are in progress.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {RESEARCH_COMPONENTS.map((component, i) => (
            <Reveal key={component.number} delay={i * 0.06}>
              <div className="h-full rounded-brand-lg border border-foreground/10 bg-foreground/[0.03] p-5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-foreground/40">{component.number}</span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-medium",
                      STATUS_CLASS[component.status],
                    )}
                  >
                    {component.status}
                  </span>
                </div>
                <h3 className="mt-3 text-base font-semibold text-foreground">{component.name}</h3>
                <p className="mt-2 text-sm leading-relaxed text-foreground/60">{component.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
