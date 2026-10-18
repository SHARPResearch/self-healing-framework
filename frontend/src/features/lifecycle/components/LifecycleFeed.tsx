import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLiveStore } from "@/shared/store/liveStore";
import { TONE_TEXT } from "../lib/format";

function time(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour12: false });
}

/** Everything the lifecycle did since this page connected, newest first (from /ws/events). */
export function LifecycleFeed() {
  const feed = useLiveStore((s) => s.feed);

  return (
    <div className="rounded-xl border border-border/60 p-4">
      <h3 className="text-base font-semibold">Lifecycle events</h3>
      <p className="mb-3 text-sm text-muted-foreground">Live from the WebSocket, newest first.</p>
      <ScrollArea className="h-80 pr-3">
        {feed.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Waiting for events. Inject a scenario on any service to start one.
          </p>
        ) : (
          <ol className="space-y-2.5">
            {feed.map((e) => (
              <li key={e.id} className="border-l-2 border-border/60 pl-3">
                <div className="flex items-baseline justify-between gap-2">
                  <span className={cn("text-xs font-medium", TONE_TEXT[e.tone])}>{e.title}</span>
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{time(e.ts)}</span>
                </div>
                <p className="line-clamp-2 text-xs text-muted-foreground" title={e.detail}>
                  {e.detail}
                </p>
              </li>
            ))}
          </ol>
        )}
      </ScrollArea>
    </div>
  );
}
