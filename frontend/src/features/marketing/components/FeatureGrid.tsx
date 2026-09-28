import { useId } from "react";
import { FEATURE_GRID, type FeatureCard as FeatureCardData } from "../data/marketingContent";
import { Reveal } from "./Reveal";

/**
 * Deterministic replacement for the reference component's Math.random-based
 * pattern -- this project avoids non-deterministic layout everywhere else
 * (the dependency graph, the incident trend chart) so screenshots and
 * renders stay reproducible, and a decorative grid highlight is no
 * exception.
 */
function seededSquares(seed: number, count = 5): [number, number][] {
  let state = seed + 1;
  const next = () => {
    state = (state * 48271) % 2147483647;
    return state / 2147483647;
  };
  return Array.from({ length: count }, () => [
    Math.floor(next() * 4) + 7,
    Math.floor(next() * 6) + 1,
  ]);
}

function GridPattern({ seed }: { seed: number }) {
  const patternId = useId();
  const squares = seededSquares(seed);
  const cell = 20;

  return (
    <svg aria-hidden="true" className="absolute inset-0 size-full">
      <defs>
        <pattern id={patternId} width={cell} height={cell} patternUnits="userSpaceOnUse" x="-12" y="4">
          <path d={`M.5 ${cell}V.5H${cell}`} fill="none" stroke="var(--color-foreground)" strokeOpacity={0.06} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
      <svg x="-12" y="4" className="overflow-visible">
        {squares.map(([sx, sy], index) => (
          <rect
            key={index}
            width={cell + 1}
            height={cell + 1}
            x={sx * cell}
            y={sy * cell}
            fill="var(--color-foreground)"
            fillOpacity={0.06}
          />
        ))}
      </svg>
    </svg>
  );
}

function FeatureTile({ feature, index }: { feature: FeatureCardData; index: number }) {
  const Icon = feature.icon;

  return (
    <div className="group relative overflow-hidden p-6">
      <div className="pointer-events-none absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100 mask-[radial-gradient(farthest-side_at_top_left,white,transparent)]">
        <GridPattern seed={index} />
      </div>
      <Icon className="relative size-6 text-foreground/70" strokeWidth={1.5} aria-hidden="true" />
      <h3 className="relative mt-8 text-sm font-medium text-foreground md:text-base">{feature.title}</h3>
      <p className="relative mt-2 text-xs leading-relaxed text-foreground/50 md:text-sm">{feature.body}</p>
    </div>
  );
}

export function FeatureGrid() {
  return (
    <section className="border-y border-foreground/10 bg-foreground/[0.02]">
      <div className="mx-auto max-w-6xl px-6 py-24">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-medium tracking-display text-foreground sm:text-4xl">
              Everything the loop needs, built in
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-foreground/60">
              Six capabilities that turn telemetry into a fix, without a human in the loop.
            </p>
          </div>
        </Reveal>

        <Reveal delay={0.15}>
          <div className="mt-14 grid grid-cols-1 divide-x divide-y divide-dashed divide-foreground/10 border border-dashed border-foreground/10 sm:grid-cols-2 md:grid-cols-3">
            {FEATURE_GRID.map((feature, i) => (
              <FeatureTile key={feature.title} feature={feature} index={i} />
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
