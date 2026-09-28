import { motion } from "framer-motion";
import { Layers } from "lucide-react";
import { RuntimeIcon } from "./RuntimeIcon";
import { AnomalyScoreBars } from "./AnomalyScoreBars";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { ServiceRow } from "../types";

const SEVERITY_ROW_GRADIENT = {
  watch: "from-status-watch/10",
  warn: "from-status-warn/10",
  degrade: "from-status-degrade/10",
  critical: "from-status-critical/10",
} as const;

interface ServiceTableRowProps {
  row: ServiceRow;
  index: number;
  onSelect: (row: ServiceRow) => void;
}

export function ServiceTableRow({ row, index, onSelect }: ServiceTableRowProps) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, x: -25, scale: 0.95, filter: "blur(4px)" },
        visible: {
          opacity: 1,
          x: 0,
          scale: 1,
          filter: "blur(0px)",
          transition: { type: "spring", stiffness: 400, damping: 28, mass: 0.6 },
        },
      }}
      className="relative cursor-pointer rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      role="button"
      tabIndex={0}
      onClick={() => onSelect(row)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(row);
        }
      }}
    >
      <motion.div
        className="relative overflow-hidden rounded-xl border border-border/50 bg-muted/50 p-4"
        whileHover={{ y: -1, transition: { type: "spring", stiffness: 400, damping: 25 } }}
      >
        <div
          className={`absolute inset-0 bg-gradient-to-l pointer-events-none ${SEVERITY_ROW_GRADIENT[row.status]} to-transparent`}
          style={{ backgroundSize: "30% 100%", backgroundPosition: "right", backgroundRepeat: "no-repeat" }}
        />

        <div className="relative grid grid-cols-12 items-center gap-4">
          <div className="col-span-1">
            <span className="text-2xl font-bold text-muted-foreground">
              {String(index + 1).padStart(2, "0")}
            </span>
          </div>

          <div className="col-span-2 flex items-center gap-3">
            <RuntimeIcon runtime={row.runtime} />
            <span className="font-medium text-foreground">{row.displayName}</span>
          </div>

          <div className="col-span-2 flex items-center gap-3">
            <div className="flex size-8 items-center justify-center rounded-full border border-border/30 bg-muted/40">
              <Layers className="size-4 text-muted-foreground" />
            </div>
            <span className="text-foreground">{row.namespace}</span>
          </div>

          <div className="col-span-2">
            <span className="font-mono text-sm text-foreground">{row.clusterIp}</span>
          </div>

          <div className="col-span-2">
            <span className="font-mono text-sm text-foreground">{row.replicas}</span>
          </div>

          <div className="col-span-2">
            <AnomalyScoreBars score={row.anomalyScore} severity={row.status} />
          </div>

          <div className="col-span-1">
            <SeverityBadge severity={row.status} />
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
