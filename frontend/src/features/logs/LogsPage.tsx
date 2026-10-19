import { useEffect, useMemo, useState } from "react";
import { Clock, Download, Pause, Play, PlugZap, Search, X } from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { LogHistogram } from "./components/LogHistogram";
import { LogTable, timezoneLabel } from "./components/LogTable";
import { useLogStream } from "./hooks/useLogStream";
import { hasTerm, parseFilter, toggleTerm } from "./lib/filter";
import { LOG_RANGES, type LogLine } from "./types";

const LEVEL_CHIPS: { value: string; label: string; dot: string }[] = [
  { value: "error", label: "Errors", dot: "bg-status-critical" },
  { value: "warn", label: "Warnings", dot: "bg-status-degrade" },
  { value: "info", label: "Info", dot: "bg-status-warn" },
];

function download(name: string, mime: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors",
        active
          ? "border-foreground/40 bg-accent text-foreground"
          : "border-border/60 text-muted-foreground hover:bg-accent/50 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

/**
 * Platform logs, Railway style: one searchable stream of everything the stack prints (the database
 * and Redis containers, the ml-backend itself) plus a line per lifecycle event of each monitored
 * service (alarms, quarantines, decisions, operator questions, model transitions).
 */
export function LogsPage() {
  const [query, setQuery] = useState("");
  const [rangeId, setRangeId] = useState("1h");
  const [live, setLive] = useState(true);
  const range = LOG_RANGES.find((r) => r.id === rangeId) ?? LOG_RANGES[2];
  const { lines, hasMore, loading, loadingOlder, error, histogram, services, loadOlder } = useLogStream({
    query,
    rangeSeconds: range.seconds,
    live,
  });
  const terms = useMemo(() => parseFilter(query).text, [query]);

  // "/" jumps to the filter box, as on Railway
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (e.key === "/" && !(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable))) {
        e.preventDefault();
        document.getElementById("log-filter")?.focus();   // Input is not a ref-forwarding component
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const exportText = (rows: LogLine[]) =>
    rows.map((l) => `${l.time} [${l.level}] ${l.service}: ${l.message}`).join("\n") + "\n";

  const stampName = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");

  return (
    <AppShell pageTitle="Logs">
      <div className="flex h-[calc(100vh-7rem)] flex-col overflow-hidden rounded-xl border border-border/60">
        <div className="flex flex-wrap items-center gap-2 p-3">
          <div className="relative min-w-64 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="log-filter"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && (e.currentTarget.blur(), setQuery(""))}
              placeholder="Filter and search logs"
              aria-label="Filter and search logs. Terms: service:name level:error source:lifecycle"
              className="h-9 pr-16 pl-9 text-sm"
              spellCheck={false}
            />
            <span className="absolute top-1/2 right-2 flex -translate-y-1/2 items-center gap-1">
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery("")}
                  aria-label="Clear filter"
                  className="rounded p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              ) : (
                <kbd className="rounded border border-border/60 px-1.5 text-[11px] text-muted-foreground">/</kbd>
              )}
            </span>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              {/* native button: shadcn's Button does not forward refs under React 18, which Radix needs */}
              <button
                type="button"
                aria-label="Download the loaded lines"
                title={`Download the ${lines.length} loaded lines`}
                disabled={!lines.length}
                className={buttonVariants({ variant: "outline", size: "icon" })}
              >
                <Download />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => download(`logs-${stampName}.log`, "text/plain", exportText(lines))}>
                As text (.log)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => download(`logs-${stampName}.json`, "application/json", JSON.stringify(lines, null, 2))}>
                As JSON
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Select value={rangeId} onValueChange={setRangeId}>
            <SelectTrigger className="h-9 w-48" aria-label="Time range">
              <Clock />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LOG_RANGES.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={() => setLive((v) => !v)}
                aria-pressed={live}
                aria-label={live ? "Pause live tail" : "Resume live tail"}
                className={cn(buttonVariants({ variant: "outline", size: "icon" }), live && "text-status-healthy")}
              >
                {live ? <Pause /> : <Play />}
              </button>
            </TooltipTrigger>
            <TooltipContent>{live ? "Live: new lines stream in. Click to pause." : "Paused. Click to resume."}</TooltipContent>
          </Tooltip>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 px-3 pb-2">
          {LEVEL_CHIPS.map((c) => (
            <Chip key={c.value} active={hasTerm(query, "level", c.value)} onClick={() => setQuery(toggleTerm(query, "level", c.value))}>
              <span className={cn("size-1.5 rounded-full", c.dot)} />
              {c.label}
            </Chip>
          ))}
          <span className="mx-1 h-4 w-px bg-border" />
          {services.map((s) => (
            <Chip
              key={s.service}
              active={hasTerm(query, "service", s.service)}
              onClick={() => setQuery(toggleTerm(query, "service", s.service))}
            >
              {s.service}
              <span className="font-mono text-[10px] opacity-60">{s.count}</span>
            </Chip>
          ))}
        </div>

        <LogHistogram data={histogram} since={new Date(Date.now() - range.seconds * 1000).toISOString()} />

        <div className="mt-2 grid grid-cols-[3px_11.5rem_9rem_1fr] gap-x-3 border-y border-border/60 pr-4 text-xs font-medium text-muted-foreground">
          <span />
          <span className="py-2">Time ({timezoneLabel()})</span>
          <span className="py-2">Service</span>
          <span className="py-2">Data</span>
        </div>

        {error && lines.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
            <PlugZap className="size-7 text-muted-foreground" />
            <p className="text-sm font-medium">Can't reach ml-backend</p>
            <p className="max-w-md text-xs text-muted-foreground">
              Start it with <span className="font-mono">uv run uvicorn app.main:app --port 8002</span> in{" "}
              <span className="font-mono">services/ml-backend</span>. {error}
            </p>
          </div>
        ) : loading && lines.length === 0 ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">Loading logs…</div>
        ) : lines.length === 0 ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            No logs match{query ? ` “${query}”` : ""} in this range.
          </div>
        ) : (
          <LogTable
            lines={lines}
            terms={terms}
            hasMore={hasMore}
            loadingOlder={loadingOlder}
            onLoadOlder={loadOlder}
            onServiceClick={(s) => setQuery(toggleTerm(query, "service", s))}
          />
        )}
      </div>
    </AppShell>
  );
}
