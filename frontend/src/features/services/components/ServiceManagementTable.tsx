import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ServiceTableRow } from "./ServiceTableRow";
import { ServiceDetailPanel } from "./ServiceDetailPanel";
import { activityLogByService as initialActivityLog, serviceRows } from "../data/mockData";
import type { ActivityLogEntry, ServiceRow } from "../types";

export function ServiceManagementTable() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activityLog, setActivityLog] = useState(initialActivityLog);

  const selectedService: ServiceRow | undefined = serviceRows.find((s) => s.serviceId === selectedId);
  const criticalCount = serviceRows.filter((s) => s.status === "critical").length;

  const handleAction = (message: string) => {
    if (!selectedId) return;
    const entry: ActivityLogEntry = {
      id: `${selectedId}-${Date.now()}`,
      message,
      timestamp: new Date().toISOString(),
    };
    setActivityLog((prev) => ({
      ...prev,
      [selectedId]: [entry, ...(prev[selectedId] ?? [])],
    }));
  };

  return (
    <div className="relative rounded-2xl border border-border/30 bg-card p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="size-2 animate-pulse rounded-full bg-status-healthy" />
            <h1 className="text-xl font-medium text-foreground">Active services</h1>
          </div>
          <div className="text-sm text-muted-foreground">
            {serviceRows.length} services &bull; {criticalCount} critical
          </div>
        </div>
      </div>

      <motion.div
        className="space-y-2"
        variants={{ visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } } }}
        initial="hidden"
        animate="visible"
      >
        <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium tracking-wider text-muted-foreground uppercase">
          <div className="col-span-1">No</div>
          <div className="col-span-2">Service name</div>
          <div className="col-span-2">Namespace</div>
          <div className="col-span-2">Cluster IP</div>
          <div className="col-span-2">Replicas</div>
          <div className="col-span-2">Anomaly score</div>
          <div className="col-span-1">Status</div>
        </div>

        {serviceRows.map((row, index) => (
          <ServiceTableRow key={row.serviceId} row={row} index={index} onSelect={(s) => setSelectedId(s.serviceId)} />
        ))}
      </motion.div>

      <AnimatePresence>
        {selectedService && (
          <ServiceDetailPanel
            service={selectedService}
            activityLog={activityLog[selectedService.serviceId] ?? []}
            onClose={() => setSelectedId(null)}
            onAction={handleAction}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
