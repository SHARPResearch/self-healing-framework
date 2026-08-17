import { useCountUp } from "@/shared/hooks/useCountUp";
import { HERO_STATS, type HeroStat } from "../data/marketingContent";

function Stat({ stat, index }: { stat: HeroStat; index: number }) {
  const { ref, display } = useCountUp({
    to: stat.to,
    decimals: stat.decimals,
    duration: 1500 + index * 80,
    delay: 480 + index * 90,
  });

  return (
    <div className="flex flex-col items-center gap-1 text-center">
      <span aria-hidden="true" className="font-display text-2xl text-white/80">
        {stat.symbol}
      </span>
      <span className="font-mono text-xl font-semibold tracking-tight text-white tabular-nums sm:text-2xl">
        {stat.prefix}
        <span ref={ref}>{display}</span>
        {stat.suffix}
      </span>
      <span className="text-xs text-white/50">{stat.label}</span>
    </div>
  );
}

export function StatsRow() {
  return (
    <div className="mt-16 grid w-full max-w-3xl grid-cols-2 gap-8 sm:grid-cols-4">
      {HERO_STATS.map((stat, i) => (
        <Stat key={stat.label} stat={stat} index={i} />
      ))}
    </div>
  );
}
