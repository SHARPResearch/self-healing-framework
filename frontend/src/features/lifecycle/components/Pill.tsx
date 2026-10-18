import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { TONE_PILL, type Tone } from "../lib/format";

export function Pill({ tone, children, className }: { tone: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        TONE_PILL[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
