import { cn } from "@/lib/utils";
import type { Runtime } from "../types";

function runtimeLabel(runtime: Runtime): string {
  const normalized = runtime.toLowerCase();
  if (normalized.startsWith("node")) return "JS";
  if (normalized.startsWith("python")) return "PY";
  if (normalized.startsWith("go")) return "GO";
  if (normalized.startsWith("java")) return "JVM";
  if (normalized.startsWith("postgres")) return "PG";
  if (normalized.startsWith("redis")) return "RD";
  if (normalized.startsWith("kafka")) return "KF";
  if (normalized.startsWith("nginx")) return "NG";
  if (normalized.startsWith("envoy")) return "EV";
  if (normalized.startsWith("rust")) return "RS";
  return runtime.slice(0, 2).toUpperCase();
}

function runtimeGradient(runtime: Runtime): string {
  if (runtime.toLowerCase().startsWith("python"))
    return "from-blue-500 to-yellow-500";
  if (runtime.toLowerCase().startsWith("go"))
    return "from-cyan-500 to-cyan-700";
  if (runtime.toLowerCase().startsWith("node"))
    return "from-green-500 to-green-700";
  return "from-muted-foreground to-muted";
}

export function RuntimeIcon({
  runtime,
  className,
}: {
  runtime: Runtime;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex size-8 items-center justify-center rounded-full border border-border/30 bg-gradient-to-br text-xs font-mono font-bold text-white",
        runtimeGradient(runtime),
        className,
      )}
    >
      {runtimeLabel(runtime)}
    </div>
  );
}
