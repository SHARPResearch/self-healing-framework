import { useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { api } from "@/lib/mlBackend";
import { refreshLive } from "@/hooks/useLiveConnection";
import { useLiveStore } from "@/shared/store/liveStore";

const SPEEDS = [15, 30, 60, 120];

/** Presenter controls: replay speed, pause, reset, and who answers operator queries. */
export function DemoControls() {
  const health = useLiveStore((s) => s.health);
  const operator = useLiveStore((s) => s.operator);
  const setOperator = useLiveStore((s) => s.setOperator);
  const setHealth = useLiveStore((s) => s.setHealth);
  const [resetting, setResetting] = useState(false);

  const speed = async (body: { eventsPerSec?: number; paused?: boolean }) => {
    const res = await api.speed(body);
    if (health) setHealth({ ...health, ...res });
  };

  const reset = async () => {
    if (!window.confirm("Reset the demo? Every service is rebuilt from its warm-up and the history is cleared.")) return;
    setResetting(true);
    try {
      await api.reset();
      await refreshLive();
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/60 px-4 py-3">
      <span className="text-xs font-medium tracking-wider text-muted-foreground uppercase">Demo</span>
      <div className="flex items-center gap-1">
        {SPEEDS.map((eps) => (
          <Button
            key={eps}
            size="sm"
            variant="ghost"
            className={cn("h-7 px-2 font-mono text-xs", health?.eventsPerSec === eps && "bg-accent")}
            onClick={() => speed({ eventsPerSec: eps })}
          >
            {eps}/s
          </Button>
        ))}
      </div>
      <Button size="sm" variant="outline" className="h-7" onClick={() => speed({ paused: !health?.paused })}>
        {health?.paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
        {health?.paused ? "Resume" : "Pause"}
      </Button>
      <Button size="sm" variant="outline" className="h-7" disabled={resetting} onClick={reset}>
        <RotateCcw className="size-3.5" />
        Reset
      </Button>
      <span className="text-xs text-muted-foreground">
        One lifecycle day = 1440 events ≈ {health ? Math.round(1440 / Math.max(health.eventsPerSec, 1)) : 24}s
      </span>
      <label className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
        Operator
        <Input
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
          className="h-7 w-32 text-xs"
          aria-label="Operator name recorded in the audit trail"
        />
      </label>
    </div>
  );
}
