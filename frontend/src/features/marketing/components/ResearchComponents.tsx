import { cn } from "@/lib/utils";
import { RESEARCH_COMPONENTS, type ResearchComponent } from "../data/marketingContent";
import { Reveal } from "./Reveal";

const STATUS_CLASS: Record<ResearchComponent["status"], string> = {
  Complete: "bg-status-healthy/15 text-status-healthy",
  "In progress": "bg-status-warn/15 text-status-warn",
  Planned: "bg-white/10 text-white/50",
};

export function ResearchComponents() {
  return (
    <section id="research" className="border-y border-white/10 bg-white/[0.02]">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <p className="text-xs font-medium tracking-widest text-white/40 uppercase">
            Research components
          </p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Five parts, built and evaluated separately
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-white/60">
            SHARP is a final year research project, and this is an honest view of where each piece
            actually is. Component 1 is complete and benchmarked; the rest are in progress.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {RESEARCH_COMPONENTS.map((component, i) => (
            <Reveal key={component.number} delay={i * 0.06}>
              <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs text-white/40">{component.number}</span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-medium",
                      STATUS_CLASS[component.status],
                    )}
                  >
                    {component.status}
                  </span>
                </div>
                <h3 className="mt-3 text-base font-semibold text-white">{component.name}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/60">{component.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
