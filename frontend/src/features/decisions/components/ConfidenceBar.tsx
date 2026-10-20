interface Props {
  detection: number;
  rule: number;
  final: number;
}

export function ConfidenceBar({ detection, rule, final }: Props) {
  const pct = (v: number) => Math.max(0, Math.min(1, v)) * 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Blended confidence</span>
        <span className="font-mono font-semibold">
          {pct(final).toFixed(1)}%
        </span>
      </div>
      <div className="relative h-3 w-full overflow-hidden rounded-full bg-muted/40">
        {/* threshold bands */}
        <div
          className="absolute inset-y-0 left-0 bg-red-500/20"
          style={{ width: "60%" }}
        />
        <div
          className="absolute inset-y-0 bg-amber-500/20"
          style={{ left: "60%", width: "25%" }}
        />
        <div
          className="absolute inset-y-0 bg-green-500/20"
          style={{ left: "85%", width: "15%" }}
        />

        {/* final value */}
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500"
          style={{
            width: `${pct(final)}%`,
            transition: "width 800ms ease-out",
          }}
        />
      </div>
      <div className="flex items-center justify-between gap-3 text-[10px] font-mono text-muted-foreground">
        <span>detection {pct(detection).toFixed(1)}%</span>
        <span>rule {pct(rule).toFixed(1)}%</span>
        <span className="text-foreground">final {pct(final).toFixed(1)}%</span>
      </div>
    </div>
  );
}
