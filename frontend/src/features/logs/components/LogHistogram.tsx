import { Bar, BarChart, ResponsiveContainer, Tooltip } from "recharts";
import type { LogHistogram as Histogram } from "../types";

const COLORS = {
  info: "var(--status-warn)",       // this app's "warn" token is blue, which reads as info here
  warn: "var(--status-degrade)",
  error: "var(--status-critical)",
};

function label(iso: string, wide: boolean): string {
  const d = new Date(iso);
  return wide
    ? d.toLocaleDateString([], { year: "numeric", month: "2-digit", day: "2-digit" }).split("/").reverse().join("-")
    : d.toLocaleTimeString([], { hour12: false });
}

/** Lines per time bucket, stacked by level: the strip above the log table. */
export function LogHistogram({ data, since }: { data: Histogram | null; since: string }) {
  // Fill empty buckets so the strip always spans the whole range, like Railway's, instead of
  // stretching the few buckets that have lines across the full width.
  const width = (data?.bucketSeconds ?? 60) * 1000;
  const counts = new Map((data?.buckets ?? []).map((b) => [new Date(b.time).getTime(), b]));
  const end = Date.now();
  const rows: { t: number; time: string; info: number; warn: number; error: number }[] = [];
  for (let t = Math.floor(new Date(since).getTime() / width) * width; t <= end; t += width) {
    const b = counts.get(t);
    rows.push({ t, time: new Date(t).toISOString(), info: b?.info ?? 0, warn: b?.warn ?? 0, error: b?.error ?? 0 });
  }
  const empty = !data || data.buckets.length === 0;
  const wide = width * 60 > 2 * 86400 * 1000;
  const first = rows[0]?.time ?? since;
  const last = rows.length ? rows[rows.length - 1].time : new Date().toISOString();

  return (
    <div className="px-4 pt-2">
      <div className="h-14">
        {empty ? (
          <div className="flex h-full items-end text-[11px] text-muted-foreground">No lines in this range.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 2, right: 0, left: 0, bottom: 0 }} barCategoryGap={1}>
              <Tooltip
                cursor={{ fill: "var(--accent)", opacity: 0.4 }}
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  fontSize: 12,
                }}
                labelFormatter={(_, p) => (p?.[0] ? new Date(p[0].payload.t).toLocaleString() : "")}
              />
              <Bar dataKey="info" stackId="l" fill={COLORS.info} isAnimationActive={false} />
              <Bar dataKey="warn" stackId="l" fill={COLORS.warn} isAnimationActive={false} />
              <Bar dataKey="error" stackId="l" fill={COLORS.error} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="flex justify-between pt-1 font-mono text-[11px] text-muted-foreground">
        <span>{label(first, wide)}</span>
        <span>{label(last, wide)}</span>
      </div>
    </div>
  );
}
