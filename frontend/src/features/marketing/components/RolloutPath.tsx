import { ROLLOUT_PILLARS, type RolloutPillar } from "../data/marketingContent";
import { Reveal } from "./Reveal";

function PillarChip({ pillar }: { pillar: RolloutPillar }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-foreground/15 bg-foreground/[0.04] px-4 py-2 text-sm font-medium whitespace-nowrap text-foreground">
      <pillar.icon className="size-4 text-foreground/70" aria-hidden="true" />
      {pillar.label}
    </div>
  );
}

function PillarItems({ pillar }: { pillar: RolloutPillar }) {
  return (
    <div className="mt-3 flex items-start gap-3">
      <div
        aria-hidden="true"
        className="mt-1 h-24 w-px shrink-0 bg-gradient-to-b from-brand-primary/50 to-transparent"
      />
      <ul className="space-y-1.5 text-left">
        {pillar.items.map((item) => (
          <li key={item} className="text-xs whitespace-nowrap text-foreground/60">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The desktop layout is a staircase of absolutely positioned pillars, rising
 * left to right. Positions are percentages of this section's own relative
 * box (not viewport units), so the staircase stays scoped to the page's
 * usual max-w-6xl column instead of the raw browser width.
 */
function DesktopStaircase() {
  return (
    <div className="relative hidden h-[420px] w-full lg:block">
      {ROLLOUT_PILLARS.map((pillar) => (
        <div
          key={pillar.label}
          className="absolute flex flex-col items-start"
          style={{ left: `${pillar.leftPct}%`, bottom: `${pillar.bottomPct}%` }}
        >
          <PillarChip pillar={pillar} />
          <PillarItems pillar={pillar} />
        </div>
      ))}
    </div>
  );
}

/** Mobile/tablet: a single column, alternating left/right per pillar. */
function MobileFlow() {
  return (
    <div className="flex w-full flex-col gap-8 lg:hidden">
      {ROLLOUT_PILLARS.map((pillar, i) => {
        const isRight = i % 2 !== 0;
        return (
          <div
            key={pillar.label}
            className="flex flex-col"
            style={{ alignItems: isRight ? "flex-end" : "flex-start" }}
          >
            <PillarChip pillar={pillar} />
            <div className="mt-3 flex w-full" style={{ flexDirection: isRight ? "row-reverse" : "row" }}>
              <div
                aria-hidden="true"
                className="w-px shrink-0 bg-gradient-to-b from-brand-primary/50 to-transparent"
                style={{ marginLeft: isRight ? 0 : 22, marginRight: isRight ? 22 : 0 }}
              />
              <ul
                className="flex flex-col gap-1.5 py-1"
                style={{ alignItems: isRight ? "flex-end" : "flex-start", textAlign: isRight ? "right" : "left" }}
              >
                {pillar.items.map((item) => (
                  <li key={item} className="text-xs text-foreground/60">
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function RolloutPath() {
  return (
    <section className="border-y border-foreground/10 bg-foreground/[0.02]">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <p className="text-xs font-medium tracking-widest text-foreground/40 uppercase">Rollout path</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-medium tracking-display text-foreground sm:text-4xl">
            Four steps to a self-healing cluster
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-foreground/60">
            Standing this up isn&apos;t a leap of faith. Each phase has a concrete checklist before
            the next one starts.
          </p>
        </Reveal>

        <Reveal delay={0.15}>
          <div className="mt-14">
            <DesktopStaircase />
            <MobileFlow />
          </div>
        </Reveal>
      </div>
    </section>
  );
}
