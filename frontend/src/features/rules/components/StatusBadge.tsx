import type { RuleStatus } from "@/lib/api";
import { statusColor } from "../types";

export function StatusBadge({ status }: { status: RuleStatus }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider ${statusColor(status)}`}
    >
      {status}
    </span>
  );
}
