import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Reveal } from "./Reveal";

export function CtaBand() {
  return (
    <section className="mx-auto max-w-6xl px-6 pb-24">
      <Reveal>
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-white/[0.01] px-8 py-16 text-center sm:px-16">
          <div
            aria-hidden="true"
            className="absolute inset-x-0 -top-24 mx-auto h-64 w-64 rounded-full bg-status-healthy/15 blur-[120px]"
          />
          <h2 className="relative text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            See the closed loop for yourself
          </h2>
          <p className="relative mx-auto mt-4 max-w-md text-sm leading-relaxed text-white/60">
            The dashboard runs on mock telemetry, so every screen is explorable without a cluster
            attached.
          </p>
          <div className="relative mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 rounded-full bg-white px-7 py-3 text-sm font-semibold text-black transition-transform hover:-translate-y-0.5 hover:scale-[1.02]"
            >
              Get started
              <ArrowRight className="size-4" />
            </Link>
            <Link
              to="/dashboard"
              className="rounded-full border border-white/20 px-7 py-3 text-sm font-medium text-white/80 transition-colors hover:bg-white/5 hover:text-white"
            >
              Explore the dashboard
            </Link>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
