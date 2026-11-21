import { useEffect, useMemo, useState } from "react";
import { Activity, Clock, ExternalLink } from "lucide-react";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/mlBackend";
import { useLiveStore } from "@/shared/store/liveStore";
import type { TelemetryEvidence as Evidence, TelemetryFeature, TelemetryMarker } from "../types";
import { ACTION_LABEL, ACTION_TONE, type Tone } from "../lib/format";

const RANGES = [
  { minutes: 30, label: "Last 30 minutes" },
  { minutes: 60, label: "Last hour" },
  { minutes: 180, label: "Last 3 hours" },
];

const TONE_STROKE: Record<Tone, string> = {
  neutral: "var(--muted-foreground)",
  info: "var(--status-warn)",
  good: "var(--status-healthy)",
  warn: "var(--status-degrade)",
  bad: "var(--status-critical)",
};

function markerTone(m: TelemetryMarker): Tone {
  if (m.event === "lifecycle_decision" && m.action) return ACTION_TONE[m.action];
  return "neutral";
}

function markerText(m: TelemetryMarker): string {
  if (m.event === "lifecycle_decision" && m.action) return `Decision: ${ACTION_LABEL[m.action]} (${m.label.split(" -> ")[0].replace(/_/g, " ")})`;
  if (m.event === "quarantine_opened") return `Quarantine opened (${(m.trigger ?? "").replace(/_/g, " ")})`;
  return m.label.charAt(0).toUpperCase() + m.label.slice(1);
}

/** A value in the feature's own unit, short enough for an axis tick or a tooltip. */
function formatValue(v: number | null | undefined, unit: TelemetryFeature["unit"]): string {
  if (v == null || Number.isNaN(v)) return "n/a";
  switch (unit) {
    case "cores":
      return `${Math.round(v * 1000)}m`;
    case "bytes":
      return `${(v / 2 ** 20).toFixed(0)} MiB`;
    case "bytes/s":
      return v >= 2 ** 20 ? `${(v / 2 ** 20).toFixed(1)} MiB/s` : `${(v / 1024).toFixed(1)} KiB/s`;
    case "ratio":
      return `${(v * 100).toFixed(0)}%`;
    case "seconds":
      return `${(v * 1000).toFixed(v < 0.01 ? 1 : 0)} ms`;
    default:
      return Number.isInteger(v) ? String(v) : v.toFixed(2);
  }
}

const clock = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/**
 * Live mode: the raw Prometheus features the detector scored for one service, with the lifecycle
 * events of the same window drawn as vertical rules. This is the evidence an operator checks
 * before trusting a quarantine verdict or answering a query, with nothing derived from the model.
 */
export function TelemetryEvidence() {
  const services = useLiveStore((s) => s.serviceOrder);
  const names = useLiveStore((s) => s.services);
  const grafanaUrl = useLiveStore((s) => s.health?.grafanaUrl);
  const scrapeSeconds = useLiveStore((s) => s.health?.scrapeSeconds) ?? 5;
  const [serviceId, setServiceId] = useState<string | null>(null);
  const [minutes, setMinutes] = useState(30);
  const [data, setData] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = serviceId ?? services[0] ?? null;

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    const load = () =>
      api
        .telemetry(selected, minutes)
        .then((d) => {
          if (!cancelled) {
            setData(d);
            setError(null);
          }
        })
        .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    load();
    const timer = setInterval(load, Math.max(scrapeSeconds * 3, 10) * 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [selected, minutes, scrapeSeconds]);

  const current = data && data.serviceId === selected ? data : null;
  const markers = useMemo(() => [...(current?.markers ?? [])].sort((a, b) => b.time - a.time), [current]);
  const grafanaLink = grafanaUrl && selected
    ? `${grafanaUrl.replace(/\/$/, "")}/d/sharp-online-boutique?var-app=${encodeURIComponent(selected)}`
    : null;

  if (!selected) return null;

  return (
    <Card className="border-border/60 gap-3 py-4">
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-sm font-medium">
              <Activity className="size-4 text-muted-foreground" />
              Telemetry evidence
            </p>
            <p className="text-xs text-muted-foreground">
              The eight Prometheus features the detector scores, unprocessed, with this service's lifecycle events.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Select value={selected} onValueChange={setServiceId}>
              <SelectTrigger className="h-9 w-56" aria-label="Service">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {services.map((id) => (
                  <SelectItem key={id} value={id}>
                    {names[id]?.displayName ?? id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={String(minutes)} onValueChange={(v) => setMinutes(Number(v))}>
              <SelectTrigger className="h-9 w-44" aria-label="Time range">
                <Clock />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RANGES.map((r) => (
                  <SelectItem key={r.minutes} value={String(r.minutes)}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {grafanaLink && (
              <a
                href={grafanaLink}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border/60 px-3 text-xs text-muted-foreground hover:text-foreground"
              >
                Grafana
                <ExternalLink className="size-3.5" />
              </a>
            )}
          </div>
        </div>

        {error && !current ? (
          <p className="text-xs text-status-critical">Telemetry unavailable: {error}</p>
        ) : !current ? (
          <p className="text-xs text-muted-foreground">Loading Prometheus history…</p>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {current.features.map((f) => (
                <FeatureChart key={f.key} feature={f} points={current.points} markers={current.markers} />
              ))}
            </div>
            {markers.length > 0 ? (
              <ul className="space-y-1 text-xs">
                {markers.slice(0, 6).map((m) => (
                  <li key={`${m.time}-${m.event}`} className="flex items-center gap-2">
                    <span className="h-3 w-0.5 rounded-full" style={{ background: TONE_STROKE[markerTone(m)] }} />
                    <span className="font-mono text-muted-foreground">{clock(m.time)}</span>
                    <span>{markerText(m)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">No quarantine, change event or decision in this window.</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function FeatureChart({
  feature,
  points,
  markers,
}: {
  feature: TelemetryFeature;
  points: Evidence["points"];
  markers: TelemetryMarker[];
}) {
  const last = points.length ? points[points.length - 1][feature.key] : null;
  return (
    <div className="rounded-lg border border-border/50 px-3 pt-2 pb-1">
      <div className="flex items-baseline justify-between gap-2">
        <p className="truncate text-xs font-medium">{feature.label}</p>
        <p className="font-mono text-xs text-muted-foreground">{formatValue(last, feature.unit)}</p>
      </div>
      <ResponsiveContainer width="100%" height={84}>
        <LineChart data={points} margin={{ top: 6, right: 4, left: 4, bottom: 0 }}>
          <XAxis dataKey="time" type="number" domain={["dataMin", "dataMax"]} hide />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip
            formatter={(value: number) => [formatValue(value, feature.unit), feature.label]}
            labelFormatter={(t) => clock(Number(t))}
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              fontSize: 12,
            }}
          />
          {markers.map((m) => (
            <ReferenceLine
              key={`${m.time}-${m.event}`}
              x={m.time}
              stroke={TONE_STROKE[markerTone(m)]}
              strokeDasharray={m.event === "lifecycle_decision" ? undefined : "3 3"}
              strokeWidth={m.event === "lifecycle_decision" ? 2 : 1}
            />
          ))}
          <Line
            type="monotone"
            dataKey={feature.key}
            stroke="var(--foreground)"
            strokeWidth={1.5}
            dot={false}
            connectNulls
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
