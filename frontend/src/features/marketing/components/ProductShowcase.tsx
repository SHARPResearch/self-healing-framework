import { Reveal } from "./Reveal";

/**
 * Real screenshots of this app's own pages, captured with Playwright into
 * public/marketing/. The reference design used a stock image of an unrelated
 * product, which would misrepresent what SHARP looks like.
 */
const SHOTS = [
  {
    src: "/marketing/dashboard.png",
    alt: "SHARP dashboard showing service health tiles, anomaly score trend and the incident feed",
    caption: "Dashboard",
    body: "Anomaly score trend with the warn and critical thresholds marked, live service health, and the recovery action log.",
  },
  {
    src: "/marketing/dependency-graph.png",
    alt: "SHARP dependency graph with service nodes coloured by severity and a critical service highlighted",
    caption: "Dependency graph",
    body: "Who calls whom, coloured by severity. Amber edges point at a service that is already critical.",
  },
];

export function ProductShowcase() {
  return (
    <section id="product" className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <p className="text-xs font-medium tracking-widest text-white/40 uppercase">The product</p>
        <h2 className="mt-3 max-w-2xl font-display text-3xl leading-tight tracking-tight text-white sm:text-4xl">
          Everything the loop does, visible
        </h2>
      </Reveal>

      <div className="mt-14 space-y-16">
        {SHOTS.map((shot, i) => (
          <Reveal key={shot.src} delay={i * 0.1}>
            <figure>
              <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] shadow-2xl">
                <img
                  src={shot.src}
                  alt={shot.alt}
                  width={1440}
                  height={900}
                  loading="lazy"
                  decoding="async"
                  className="w-full"
                />
              </div>
              <figcaption className="mt-4 flex flex-col gap-1">
                <span className="text-sm font-semibold text-white">{shot.caption}</span>
                <span className="max-w-2xl text-sm text-white/60">{shot.body}</span>
              </figcaption>
            </figure>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
