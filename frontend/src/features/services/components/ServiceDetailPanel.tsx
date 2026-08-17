import { motion } from "framer-motion";
import { PlusCircle, RotateCcw, Route, X } from "lucide-react";
import { RuntimeIcon } from "./RuntimeIcon";
import { AnomalyScoreBars } from "./AnomalyScoreBars";
import { SeverityBadge } from "@/shared/components/SeverityBadge";
import type { ActivityLogEntry, ServiceRow } from "../types";

interface ServiceDetailPanelProps {
  service: ServiceRow;
  activityLog: ActivityLogEntry[];
  onClose: () => void;
  onAction: (message: string) => void;
}

export function ServiceDetailPanel({ service, activityLog, onClose, onAction }: ServiceDetailPanelProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="absolute inset-0 z-10 flex flex-col overflow-hidden rounded-2xl bg-background/60 backdrop-blur-sm"
    >
      <div className="relative flex items-center justify-between border-b border-border/30 bg-gradient-to-r from-muted/50 to-transparent p-4">
        <div className="flex items-center gap-4">
          <div className="text-2xl font-bold text-muted-foreground">
            {service.serviceId.slice(-2).toUpperCase()}
          </div>
          <RuntimeIcon runtime={service.runtime} />
          <div>
            <h3 className="text-lg font-bold text-foreground">{service.displayName}</h3>
            <span className="text-sm text-muted-foreground">{service.namespace} namespace</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <motion.button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-orange-500/30 bg-orange-500/10 px-3 py-1.5 text-sm text-orange-400 transition-colors hover:bg-orange-500/20"
            onClick={() => onAction("Restart dispatched by operator")}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <RotateCcw className="size-3" />
            Restart
          </motion.button>

          <motion.button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-sm text-blue-400 transition-colors hover:bg-blue-500/20"
            onClick={() => onAction("Scale +1 replica dispatched by operator")}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <PlusCircle className="size-3" />
            Scale +1
          </motion.button>

          <motion.button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-sm text-violet-400 transition-colors hover:bg-violet-500/20"
            onClick={() => onAction("Traffic shift 50% dispatched by operator")}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Route className="size-3" />
            Shift traffic
          </motion.button>

          <motion.button
            type="button"
            className="ml-2 flex size-8 items-center justify-center rounded-full border border-border/50 bg-background/80 hover:bg-background"
            onClick={onClose}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <X className="size-4" />
          </motion.button>
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-border/30 bg-muted/40 p-3">
            <label className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Cluster IP
            </label>
            <div className="mt-1 font-mono text-sm font-medium">{service.clusterIp}</div>
          </div>

          <div className="rounded-lg border border-border/30 bg-muted/40 p-3">
            <label className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Replicas
            </label>
            <div className="mt-1 text-sm font-medium">{service.replicas}</div>
          </div>

          <div className="rounded-lg border border-border/30 bg-muted/40 p-3">
            <label className="text-xs font-medium tracking-wider text-muted-foreground uppercase">
              Status
            </label>
            <div className="mt-1">
              <SeverityBadge severity={service.status} />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border/30 bg-muted/40 p-3">
          <label className="mb-2 block text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Anomaly score
          </label>
          <AnomalyScoreBars score={service.anomalyScore} severity={service.status} />
        </div>

        <div className="rounded-lg border border-border/30 bg-muted/40 p-3">
          <label className="mb-2 block text-xs font-medium tracking-wider text-muted-foreground uppercase">
            Recent activity
          </label>
          <div className="max-h-24 space-y-1 overflow-y-auto font-mono text-xs">
            {activityLog.map((entry) => (
              <div key={entry.id} className="text-muted-foreground">
                [{new Date(entry.timestamp).toLocaleTimeString()}] {entry.message}
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
