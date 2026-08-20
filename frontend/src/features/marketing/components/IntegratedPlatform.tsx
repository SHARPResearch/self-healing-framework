import { STACK } from "../data/marketingContent";
import { Reveal } from "./Reveal";

/**
 * Replaces TechStack.tsx, restyled into the reference design's "Single
 * Integrated Platform" layout: a connector-line list on the left, a layered
 * isometric graphic on the right built from plain divs/CSS transforms rather
 * than a new dependency.
 */
export function IntegratedPlatform() {
  return (
    <section className="mx-auto max-w-6xl px-6 py-24">
      <Reveal>
        <div className="mx-auto mb-14 flex justify-center">
          <span className="rounded-full border border-foreground/15 bg-foreground/[0.04] px-4 py-1.5 text-xs text-foreground/60">
            One platform, six layers
          </span>
        </div>
      </Reveal>

      <div className="grid gap-16 lg:grid-cols-2 lg:items-center">
        <Reveal>
          <h2 className="text-3xl font-medium tracking-display text-foreground sm:text-4xl">
            A single integrated platform
          </h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-foreground/60">
            Each layer uses the ecosystem with the strongest libraries for that job, wired together
            end to end rather than bolted on afterward.
          </p>

          <ol className="mt-10 space-y-0">
            {STACK.map((item, i) => (
              <li key={item.layer} className="relative pb-8 pl-8 last:pb-0">
                {i < STACK.length - 1 && (
                  <span
                    aria-hidden="true"
                    className="absolute top-2 left-[3px] h-full w-px bg-foreground/10"
                  />
                )}
                {/* Small accent dot -- exempt from the sparse green rule. */}
                <span
                  aria-hidden="true"
                  className="absolute top-1.5 left-0 size-[7px] rounded-full bg-brand-primary"
                />
                <p className="text-sm font-medium text-foreground">{item.layer}</p>
                <p className="mt-0.5 font-mono text-xs text-foreground/50">{item.tech}</p>
                <p className="mt-1 text-xs text-foreground/40">{item.why}</p>
              </li>
            ))}
          </ol>
        </Reveal>

        <Reveal delay={0.15}>
          <div className="relative flex items-center justify-center py-8">
            <div className="flex flex-col items-center">
              {STACK.map((item, i) => (
                <div
                  key={item.layer}
                  className="relative -mt-3 flex h-16 items-center justify-center rounded-brand-md border border-foreground/10 bg-gradient-to-br from-foreground/[0.06] to-foreground/[0.01] px-8 text-center shadow-lg backdrop-blur-sm first:mt-0"
                  style={{
                    width: `${280 - i * 18}px`,
                    transform: `translateX(${i % 2 === 0 ? -1 : 1}px)`,
                  }}
                >
                  <span className="text-xs font-medium text-foreground/70">{item.layer}</span>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
