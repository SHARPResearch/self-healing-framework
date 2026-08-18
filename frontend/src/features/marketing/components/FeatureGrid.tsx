import { FEATURE_GRID } from "../data/marketingContent";
import { Reveal } from "./Reveal";

export function FeatureGrid() {
  return (
    <section className="border-y border-white/10 bg-white/[0.02]">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            Built to help operators ship reliability with less toil
          </h2>
        </Reveal>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURE_GRID.map((feature, i) => (
            <Reveal key={feature.title} delay={i * 0.05}>
              <div className="h-full rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                <div
                  aria-hidden="true"
                  className="mb-4 flex size-9 items-center justify-center rounded-lg bg-white/[0.06] font-mono text-xs text-white/50"
                >
                  {String(i + 1).padStart(2, "0")}
                </div>
                <h3 className="text-sm font-semibold text-white">{feature.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-white/60">{feature.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
