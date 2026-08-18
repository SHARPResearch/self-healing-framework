import { ANALOGY_ROWS } from "../data/marketingContent";
import { Reveal } from "./Reveal";

export function HospitalAnalogy() {
  return (
    <section className="border-y border-white/10 bg-white/[0.02]">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
          <Reveal>
            <p className="text-xs font-medium tracking-widest text-white/40 uppercase">
              In plain english
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Think of it as a hospital monitor for your cluster
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-white/60">
              A ward does not wait for a patient to collapse before reacting. Vitals are watched
              continuously, abnormal readings are caught early, and there is a standing protocol for
              what to do at each level of severity. SHARP does the same thing for microservices.
            </p>
          </Reveal>

          <Reveal delay={0.12}>
            <div className="overflow-hidden rounded-2xl border border-white/10">
              {ANALOGY_ROWS.map((row, i) => (
                <div
                  key={row.real}
                  className={`grid grid-cols-2 gap-4 p-4 ${
                    i % 2 === 0 ? "bg-white/[0.03]" : "bg-transparent"
                  }`}
                >
                  <span className="text-sm text-white">{row.real}</span>
                  <span className="text-sm text-white/50">{row.analogy}</span>
                </div>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
