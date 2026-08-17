import { cn } from "@/lib/utils";
import type { Runtime } from "../types";

const RUNTIME_LABEL: Record<Runtime, string> = {
  node: "JS",
  python: "PY",
  go: "GO",
};

const RUNTIME_GRADIENT: Record<Runtime, string> = {
  node: "from-green-500 to-green-700",
  python: "from-blue-500 to-yellow-500",
  go: "from-cyan-500 to-cyan-700",
};

export function RuntimeIcon({ runtime, className }: { runtime: Runtime; className?: string }) {
  return (
    <div
      className={cn(
        "flex size-8 items-center justify-center rounded-full border border-border/30 bg-gradient-to-br text-xs font-mono font-bold text-white",
        RUNTIME_GRADIENT[runtime],
        className,
      )}
    >
      {RUNTIME_LABEL[runtime]}
    </div>
  );
}
