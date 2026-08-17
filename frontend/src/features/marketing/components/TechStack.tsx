import { STACK } from "../data/marketingContent";
import { Reveal } from "./Reveal";

export function TechStack() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <p className="text-xs font-medium tracking-widest text-white/40 uppercase">The stack</p>
        <h2 className="mt-3 max-w-2xl font-display text-3xl leading-tight tracking-tight text-white sm:text-4xl">
          Each language doing what it is best at
        </h2>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-white/60">
          Rather than forcing one runtime everywhere, each layer uses the ecosystem with the
          strongest libraries for that job.
        </p>
      </Reveal>

      <div className="mt-14 overflow-hidden rounded-2xl border border-white/10">
        {STACK.map((item, i) => (
          <Reveal key={item.layer} delay={i * 0.05}>
            <div
              className={`grid gap-2 p-5 sm:grid-cols-3 sm:gap-6 ${
                i % 2 === 0 ? "bg-white/[0.03]" : "bg-transparent"
              }`}
            >
              <span className="text-sm font-medium text-white">{item.layer}</span>
              <span className="font-mono text-sm text-white/70">{item.tech}</span>
              <span className="text-sm text-white/50">{item.why}</span>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
