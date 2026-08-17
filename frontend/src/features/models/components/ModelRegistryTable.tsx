import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StageBadge } from "./StageBadge";
import type { ModelRun } from "../types";

interface ModelRegistryTableProps {
  runs: ModelRun[];
  onSelect: (run: ModelRun) => void;
}

export function ModelRegistryTable({ runs, onSelect }: ModelRegistryTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border/60">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Service</TableHead>
            <TableHead>Stage</TableHead>
            <TableHead className="text-right">Version</TableHead>
            <TableHead className="text-right">Mean score</TableHead>
            <TableHead className="text-right">Drift events</TableHead>
            <TableHead className="text-right">F1</TableHead>
            <TableHead>Run</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => (
            <TableRow
              key={run.runId}
              tabIndex={0}
              role="button"
              aria-label={`Open details for ${run.serviceName}`}
              onClick={() => onSelect(run)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(run);
                }
              }}
              className="cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset"
            >
              <TableCell>
                <div className="font-medium">{run.serviceName}</div>
                <div className="font-mono text-xs text-muted-foreground">{run.entityId}</div>
              </TableCell>
              <TableCell>
                <StageBadge stage={run.stage} />
              </TableCell>
              <TableCell className="text-right font-mono">v{run.version}</TableCell>
              <TableCell className="text-right font-mono">
                {run.metrics.rollingMeanScore.toFixed(2)}
              </TableCell>
              <TableCell className="text-right font-mono">
                {run.metrics.cumulativeDriftCount}
              </TableCell>
              <TableCell className="text-right font-mono">
                {run.stage === "WARM_UP" ? (
                  <span className="text-muted-foreground">--</span>
                ) : (
                  run.metrics.evalF1.toFixed(4)
                )}
              </TableCell>
              <TableCell className="font-mono text-xs text-muted-foreground">
                {run.runId.slice(0, 8)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
