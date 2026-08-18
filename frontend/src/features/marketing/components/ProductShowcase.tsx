import { Reveal } from "./Reveal";

/**
 * Real screenshot of this app's own dependency graph page, captured with
 * Playwright into public/marketing/. The dashboard screenshot lives in the
 * hero instead of here now. The reference design used a stock image of an
 * unrelated product, which would misrepresent what SHARP looks like.
 */
export function ProductShowcase() {
  return (
    <section id="product" className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <p className="text-xs font-medium tracking-widest text-white/40 uppercase">The product</p>
        <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          Everything the loop does, visible
        </h2>
      </Reveal>

      <Reveal delay={0.1}>
        <figure className="mt-14">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] shadow-2xl">
            <img
              src="/marketing/dependency-graph.png"
              alt="SHARP dependency graph with service nodes coloured by severity and a critical service highlighted"
              width={1440}
              height={900}
              loading="lazy"
              decoding="async"
              className="w-full"
            />
          </div>
          <figcaption className="mt-4 flex flex-col gap-1">
            <span className="text-sm font-semibold text-white">Dependency graph</span>
            <span className="max-w-2xl text-sm text-white/60">
              Who calls whom, coloured by severity. Amber edges point at a service that is already
              critical, so the caller is one step from cascading failure.
            </span>
          </figcaption>
        </figure>
      </Reveal>
    </section>
  );
}
