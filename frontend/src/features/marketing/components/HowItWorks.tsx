import { ArrowRight, RotateCw } from "lucide-react";
import { LOOP_STEPS } from "../data/marketingContent";
import { Reveal } from "./Reveal";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">How it works</p>
        <h2 className="mt-3 max-w-2xl text-3xl font-medium tracking-display text-foreground sm:text-4xl">
          A closed loop, not a dashboard you stare at
        </h2>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-foreground/60">
          Most monitoring tells you something broke. SHARP closes the loop: it scores the telemetry,
          decides what to do, does it, and feeds the outcome back into the model.
        </p>
      </Reveal>

      <div className="mt-14 grid gap-4 md:grid-cols-4">
        {LOOP_STEPS.map((step, i) => (
          <Reveal key={step.index} delay={i * 0.08}>
            <div className="relative h-full rounded-brand-lg border border-foreground/10 bg-foreground/[0.03] p-5">
              <span className="font-mono text-xs text-foreground/40">{step.index}</span>
              <h3 className="mt-3 text-base font-semibold text-foreground">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-foreground/60">{step.body}</p>

              {i < LOOP_STEPS.length - 1 && (
                <ArrowRight
                  aria-hidden="true"
                  className="absolute top-1/2 -right-3 hidden size-5 -translate-y-1/2 text-foreground/25 md:block"
                />
              )}
            </div>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.3}>
        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-foreground/40">
          <RotateCw className="size-3.5" />
          The outcome of every action feeds back into step 01
        </div>
      </Reveal>
    </section>
  );
}
