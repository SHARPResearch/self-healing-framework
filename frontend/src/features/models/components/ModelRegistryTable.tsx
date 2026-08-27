import { Loader2, RefreshCw } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { StageBadge } from "./StageBadge";
import type { ModelRun } from "../types";

interface ModelRegistryTableProps {
  runs: ModelRun[];
  updatingIds: Set<string>;
  onSelect: (run: ModelRun) => void;
  onUpdate: (run: ModelRun) => void;
}

function ScoreBar({ value, decimals }: { value: number; decimals: number }) {
  return (
    <div className="flex items-center justify-end gap-2">
      <Progress value={value * 100} className="h-1.5 w-14" />
      <span className="w-12 text-right font-mono text-xs">{value.toFixed(decimals)}</span>
    </div>
  );
}

export function ModelRegistryTable({ runs, updatingIds, onSelect, onUpdate }: ModelRegistryTableProps) {
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
            <TableHead className="text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.map((run) => {
            const isDriftAlerted = run.metrics.cumulativeDriftCount > 0;
            const isUpdating = updatingIds.has(run.runId);

            return (
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
                <TableCell className="text-right">
                  <ScoreBar value={run.metrics.rollingMeanScore} tone="score" />
                </TableCell>
                <TableCell className="text-right font-mono">
                  <span className={isDriftAlerted ? "text-status-warn font-medium" : undefined}>
                    {run.metrics.cumulativeDriftCount}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  {run.stage === "WARM_UP" ? (
                    <span className="font-mono text-xs text-muted-foreground">--</span>
                  ) : (
                    <ScoreBar value={run.metrics.evalF1} tone="f1" />
                  )}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {run.runId.slice(0, 8)}
                </TableCell>
                <TableCell className="text-right">
                  {isDriftAlerted && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={isUpdating}
                      onClick={(e) => {
                        e.stopPropagation();
                        onUpdate(run);
                      }}
                      aria-label={`Update ${run.serviceName} model`}
                      className="h-7 px-2"
                    >
                      {isUpdating ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="size-3.5" />
                      )}
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
