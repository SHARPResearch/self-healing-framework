import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./Reveal";

export function CtaBand() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-24">
      <Reveal>
        <div className="relative overflow-hidden rounded-brand-xl border border-foreground/10 bg-gradient-to-br from-foreground/[0.06] to-foreground/[0.01] px-8 py-16 text-center sm:px-16">
          <h2 className="relative text-3xl font-medium tracking-display text-foreground sm:text-4xl">
            See the closed loop for yourself
          </h2>
          <p className="relative mx-auto mt-4 max-w-md text-sm leading-relaxed text-foreground/60">
            The dashboard runs on mock telemetry, so every screen is explorable without a cluster
            attached.
          </p>
          <div className="relative mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 rounded-brand-sm bg-brand-primary px-7 py-3 text-sm font-semibold text-brand-on-primary transition-transform hover:-translate-y-0.5 hover:scale-[1.02]"
            >
              Get started
              <ArrowRight className="size-4" />
            </Link>
            <Link
              to="/dashboard"
              className="rounded-brand-sm border border-foreground/20 px-7 py-3 text-sm font-medium text-foreground/80 transition-colors hover:bg-foreground/5 hover:text-foreground"
            >
              Explore the dashboard
            </Link>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
