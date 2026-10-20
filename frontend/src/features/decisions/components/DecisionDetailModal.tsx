import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  X,
  AlertTriangle,
  Zap,
  ShieldCheck,
  ListFilter,
  Network,
} from "lucide-react";
import type { ApiDecision } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { SeverityGauge } from "./SeverityGauge";
import { ConfidenceBar } from "./ConfidenceBar";
import { DecisionFlow } from "./DecisionFlow";

interface Props {
  decision: ApiDecision | null;
  onClose: () => void;
}

export function DecisionDetailModal({ decision, onClose }: Props) {
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!decision) return null;
  const d = decision;

  const goToAnomalies = () => {
    onClose();
    navigate(`/anomalies?service=${encodeURIComponent(d.service_id)}`);
  };
  const goToGraph = () => {
    onClose();
    navigate(`/dependency-graph?highlight=${encodeURIComponent(d.service_id)}`);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="relative max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-xl border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 border-b border-border bg-background/95 p-4 backdrop-blur">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <SeverityGauge
                value={d.severity.normalized}
                label={d.severity.label}
                size={72}
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold">{d.service_id}</span>
                  <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-blue-600">
                    {d.action}
                  </span>
                </div>
                <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                  {d.decision_id}
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                  anomaly: {d.anomaly_id}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goToAnomalies}
                  >
                    <ListFilter className="size-3.5" />
                    View anomalies
                  </Button>
                  <Button variant="outline" size="sm" onClick={goToGraph}>
                    <Network className="size-3.5" />
                    View in Graph
                  </Button>
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="grid gap-4 p-4 md:grid-cols-[1fr_280px]">
          {/* Left: the flow */}
          <div>
            <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              <Zap className="size-3.5" />
              Decision reasoning
            </div>
            <DecisionFlow decision={d} />
          </div>

          {/* Right: summary panel */}
          <aside className="space-y-3">
            <div className="rounded-lg border border-border/60 bg-card/40 p-3">
              <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Confidence
              </p>
              <ConfidenceBar
                detection={d.confidence.detection}
                rule={d.confidence.rule}
                final={d.confidence.final}
              />
            </div>

            <div className="rounded-lg border border-border/60 bg-card/40 p-3">
              <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Risk assessment
              </p>
              <div className="space-y-1.5 text-xs">
                <Row label="Base risk" value={d.base_risk} />
                <Row
                  label="Blast factor"
                  value={d.blast_factor.toFixed(3)}
                  mono
                />
                <Row label="Centrality" value={d.centrality.toFixed(3)} mono />
              </div>
            </div>

            <div className="rounded-lg border border-border/60 bg-card/40 p-3">
              <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Policy
              </p>
              <div className="flex items-center gap-2 text-xs">
                {d.policy.outcome === "AUTO_EXECUTE" && (
                  <ShieldCheck className="size-4 text-green-600" />
                )}
                {d.policy.outcome === "HUMAN_LOOP" && (
                  <AlertTriangle className="size-4 text-amber-600" />
                )}
                <span className="font-mono font-medium">
                  {d.policy.outcome ?? "PENDING"}
                </span>
              </div>
              {d.policy.reason && (
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  {d.policy.reason}
                </p>
              )}
            </div>

            <div className="rounded-lg border border-border/60 bg-card/40 p-3">
              <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Metadata
              </p>
              <div className="space-y-1.5 text-[11px]">
                <Row label="Rule" value={d.rule_id ?? "—"} mono />
                <Row
                  label="Version"
                  value={d.rule_version?.toString() ?? "—"}
                  mono
                />
                <Row
                  label="Created"
                  value={new Date(d.created_at).toLocaleString()}
                />
              </div>
            </div>

            {/* Action params */}
            {d.action_params && Object.keys(d.action_params).length > 0 && (
              <div className="rounded-lg border border-border/60 bg-card/40 p-3">
                <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                  Action parameters
                </p>
                <div className="space-y-1 text-[11px]">
                  {Object.entries(d.action_params).map(([k, v]) => (
                    <Row key={k} label={k} value={String(v)} mono />
                  ))}
                </div>
              </div>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={`text-right ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}
