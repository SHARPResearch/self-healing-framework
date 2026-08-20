import { MARQUEE_ITEMS } from "../data/marketingContent";

/**
 * Replaces the reference design's customer logo cloud -- this is a research
 * project with no customers, so it shows what SHARP actually runs on instead
 * of fabricating enterprise logos.
 */
export function TechMarquee() {
  return (
    <section className="border-y border-foreground/10 bg-foreground/[0.02] py-8">
      <div className="mx-auto max-w-6xl px-6">
        <p className="mb-5 text-center text-xs text-foreground/40">Built on</p>
        <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
          {MARQUEE_ITEMS.map((item) => (
            <span key={item} className="font-mono text-sm text-foreground/50">
              {item}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
