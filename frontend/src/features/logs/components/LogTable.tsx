import { Fragment, useCallback, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LogLevel, LogLine } from "../types";

const LEVEL_BAR: Record<LogLevel, string> = {
  debug: "bg-muted-foreground/40",
  info: "bg-status-warn",
  warn: "bg-status-degrade",
  error: "bg-status-critical",
};

const ROW_TINT: Record<LogLevel, string> = {
  debug: "",
  info: "",
  warn: "bg-status-degrade/[0.07]",
  error: "bg-status-critical/10",
};

function stamp(iso: string): string {
  const d = new Date(iso);
  const p = (n: number, w = 2) => String(n).padStart(w, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** The time column header, e.g. "Time (GMT+5:30)". */
export function timezoneLabel(): string {
  const offset = -new Date().getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const h = Math.floor(Math.abs(offset) / 60);
  const m = Math.abs(offset) % 60;
  return `GMT${sign}${h}${m ? `:${String(m).padStart(2, "0")}` : ""}`;
}

function Highlight({ text, terms }: { text: string; terms: string[] }) {
  const needles = terms.filter(Boolean);
  if (!needles.length) return <>{text}</>;
  const escaped = needles.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const parts = text.split(new RegExp(`(${escaped.join("|")})`, "gi"));
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <mark key={i} className="rounded-sm bg-status-degrade/30 text-foreground">
            {part}
          </mark>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

interface LogTableProps {
  lines: LogLine[];
  terms: string[];
  hasMore: boolean;
  loadingOlder: boolean;
  onLoadOlder: () => void;
  onServiceClick: (service: string) => void;
}

/**
 * Oldest line at the top, newest at the bottom, like a terminal. It follows new lines while you
 * are at the bottom, stops following when you scroll up, and loads older pages when you reach the
 * top (keeping what you were looking at in place).
 */
export function LogTable({ lines, terms, hasMore, loadingOlder, onLoadOlder, onServiceClick }: LogTableProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const restore = useRef<{ height: number; top: number } | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [away, setAway] = useState(false);
  const seen = useRef(lines.length);
  const [unseen, setUnseen] = useState(0);

  const toBottom = useCallback(() => {
    const el = scroller.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    stick.current = true;
    setAway(false);
    setUnseen(0);
  }, []);

  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    if (restore.current) {
      el.scrollTop = el.scrollHeight - restore.current.height + restore.current.top;
      restore.current = null;
    } else if (stick.current) {
      el.scrollTop = el.scrollHeight;
    } else if (lines.length > seen.current) {
      setUnseen((n) => n + (lines.length - seen.current));
    }
    seen.current = lines.length;
  }, [lines]);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    stick.current = atBottom;
    setAway(!atBottom);
    if (atBottom) setUnseen(0);
    if (el.scrollTop < 48 && hasMore && !loadingOlder) {
      restore.current = { height: el.scrollHeight, top: el.scrollTop };
      onLoadOlder();
    }
  };

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scroller} onScroll={onScroll} className="scrollbar-hidden h-full overflow-y-auto font-mono text-[12.5px]">
        {loadingOlder && (
          <div className="flex items-center justify-center gap-2 py-2 text-xs text-muted-foreground">
            <Loader2 className="size-3 animate-spin" /> Loading older lines
          </div>
        )}
        {!hasMore && lines.length > 0 && (
          <div className="py-2 text-center text-[11px] text-muted-foreground">Start of the logs in this range</div>
        )}
        {lines.map((line) => {
          const open = expanded === line.id;
          return (
            <div key={line.id} className={cn("border-b border-border/30", ROW_TINT[line.level])}>
              <button
                type="button"
                onClick={() => setExpanded(open ? null : line.id)}
                className="grid w-full grid-cols-[3px_11.5rem_9rem_1fr] items-start gap-x-3 pr-4 text-left hover:bg-accent/40 focus-visible:bg-accent/40 focus-visible:outline-none"
                aria-expanded={open}
              >
                <span className={cn("h-full min-h-6 self-stretch", LEVEL_BAR[line.level])} />
                <span className="py-1 text-muted-foreground">{stamp(line.time)}</span>
                <span
                  className="truncate py-1 text-muted-foreground hover:text-foreground"
                  title={`Filter to ${line.service}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onServiceClick(line.service);
                  }}
                >
                  {line.service}
                </span>
                <span className={cn("py-1 break-words", open ? "whitespace-pre-wrap" : "line-clamp-2")}>
                  <Highlight text={line.message} terms={terms} />
                </span>
              </button>
              {open && (
                <div className="grid grid-cols-[3px_11.5rem_9rem_1fr] gap-x-3 bg-muted/30 pr-4 pb-2 text-[11.5px] text-muted-foreground">
                  <span className={LEVEL_BAR[line.level]} />
                  <span className="col-span-3 space-y-0.5 py-1">
                    <div>
                      {new Date(line.time).toISOString()} · {line.level} · {line.source}
                      {line.serviceId ? ` · ${line.serviceId}` : ""}
                    </div>
                    {Object.keys(line.attrs).length > 0 && (
                      <pre className="overflow-x-auto">{JSON.stringify(line.attrs, null, 2)}</pre>
                    )}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {away && (
        <button
          type="button"
          onClick={toBottom}
          aria-label="Scroll to the newest lines"
          className="absolute right-5 bottom-4 flex items-center gap-1.5 rounded-full border border-border bg-popover px-3 py-1.5 text-xs shadow-md hover:bg-accent"
        >
          <ArrowDown className="size-3.5" />
          {unseen > 0 ? `${unseen} new` : "Latest"}
        </button>
      )}
    </div>
  );
}
