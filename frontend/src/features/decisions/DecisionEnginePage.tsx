import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowUpRight,
  Cpu,
  Eye,
  GitBranch,
  Sliders,
  UserCheck,
  Zap,
} from "lucide-react";
import { AppShell } from "@/shared/layout/AppShell";
import { usePoll } from "@/hooks/usePoll";
import {
  fetchAnomaliesWithDecisions,
  fetchDecisions,
  fetchExecutions,
  fetchGraph,
} from "@/lib/api";

const LINKS = [
  {
    to: "/dependency-graph",
    label: "Dependency graph",
    detail: "Live call graph and blast radius",
    icon: GitBranch,
  },
  {
    to: "/anomalies",
    label: "Anomalies",
    detail: "Detections with joined decisions",
    icon: AlertTriangle,
  },
  {
    to: "/decisions",
    label: "Decisions",
    detail: "Rule selection and policy outcome",
    icon: Zap,
  },
  {
    to: "/executions",
    label: "Executions",
    detail: "Executor result and guardrails",
    icon: Cpu,
  },
  {
    to: "/escalations",
    label: "Escalations",
    detail: "Human-in-the-loop approvals",
    icon: UserCheck,
  },
  {
    to: "/shadow",
    label: "Shadow mode",
    detail: "Counterfactual action review",
    icon: Eye,
  },
  {
    to: "/rules",
    label: "Rules",
    detail: "Priorities, conditions and actions",
    icon: Sliders,
  },
];

export function DecisionEnginePage() {
  const anomalies = usePoll(() => fetchAnomaliesWithDecisions(200), {
    pollMs: 15000,
    key: "decision-engine-anomalies",
  });
  const decisions = usePoll(() => fetchDecisions(200), {
    pollMs: 15000,
    key: "decision-engine-decisions",
  });
  const executions = usePoll(() => fetchExecutions(200), {
    pollMs: 15000,
    key: "decision-engine-executions",
  });
  const graph = usePoll(() => fetchGraph(), {
    pollMs: 15000,
    key: "decision-engine-graph",
  });

  const anomalyRows = anomalies.data ?? [];
  const decisionRows = decisions.data ?? [];
  const executionRows = executions.data ?? [];
  const undecided = anomalyRows.filter((row) => !row.decision_id).length;
  const graphData = graph.data;

  const tiles = [
    { label: "Anomalies", value: anomalyRows.length, sub: `${undecided} undecided` },
    { label: "Decisions", value: decisionRows.length, sub: "rule outcomes" },
    { label: "Executions", value: executionRows.length, sub: "executor rows" },
    { label: "Graph nodes", value: graphData?.nodes.length ?? 0, sub: `${graphData?.edges.length ?? 0} edges` },
  ];

  return (
    <AppShell pageTitle="Decision Engine">
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-semibold">Decision Engine overview</h2>
          <p className="text-sm text-muted-foreground">
            Follow one signal from detection to decision, execution and review.
          </p>
        </div>

        <div className="rounded-lg border border-border/60 px-3 py-2 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">Topology: </span>
          {graphData
            ? `${graphData.source} / nodes ${graphData.node_source} / edges ${graphData.edge_source}`
            : "loading"}
          {graphData?.version ? (
            <span className="font-mono"> · {graphData.version}</span>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          {tiles.map((tile) => (
            <div key={tile.label} className="rounded-xl border border-border/60 p-3">
              <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                {tile.label}
              </p>
              <p className="mt-1 font-mono text-2xl leading-none">{tile.value}</p>
              <p className="mt-1 text-[10px] text-muted-foreground">{tile.sub}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="group flex items-start gap-3 rounded-xl border border-border/60 p-3 transition-colors hover:bg-accent/50"
            >
              <link.icon className="mt-0.5 size-4 text-muted-foreground group-hover:text-primary" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{link.label}</p>
                <p className="text-[11px] text-muted-foreground">{link.detail}</p>
              </div>
              <ArrowUpRight className="size-3.5 text-muted-foreground group-hover:text-primary" />
            </Link>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
