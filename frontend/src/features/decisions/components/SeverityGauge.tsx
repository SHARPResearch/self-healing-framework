interface Props {
  value: number; // 0..1 normalized
  label: string; // "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
  size?: number;
}

const COLORS: Record<string, { stroke: string; text: string; ring: string }> = {
  LOW: { stroke: "#22c55e", text: "text-green-600", ring: "ring-green-500/30" },
  MEDIUM: {
    stroke: "#f59e0b",
    text: "text-amber-600",
    ring: "ring-amber-500/30",
  },
  HIGH: {
    stroke: "#f97316",
    text: "text-orange-600",
    ring: "ring-orange-500/30",
  },
  CRITICAL: {
    stroke: "#ef4444",
    text: "text-red-600",
    ring: "ring-red-500/30",
  },
};

export function SeverityGauge({ value, label, size = 84 }: Props) {
  const cfg = COLORS[label] ?? COLORS.LOW;
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - Math.max(0, Math.min(1, value)));

  return (
    <div
      className={`relative flex items-center justify-center rounded-full ring-2 ${cfg.ring}`}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="currentColor"
          strokeWidth={6}
          fill="none"
          className="text-muted/30"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={cfg.stroke}
          strokeWidth={6}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 800ms ease-out" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-lg font-bold ${cfg.text}`}>
          {Math.round(value * 100)}%
        </span>
        <span className="text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      </div>
    </div>
  );
}
