import {
  Activity,
  Bot,
  GitBranch,
  History,
  Plug,
  Rocket,
  Route,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import {
  siDotnet,
  siKubernetes,
  siMlflow,
  siPrometheus,
  siReact,
  siRedis,
  siTimescale,
  type SimpleIcon,
} from "simple-icons";
import type { Severity } from "@/shared/types";

export interface HeroStat {
  symbol: string;
  to: number;
  decimals: number;
  prefix?: string;
  suffix?: string;
  label: string;
}

/**
 * Every figure here is doc grounded. Accuracy is deliberately absent:
 * ml-pipeline/RESULTS.md measures F1 at 0.5663 on the single tuned entity but
 * 0.1195 averaged across all 28, so a headline accuracy number would be either
 * cherry picked or bad. Throughput, update cost, detection latency and
 * benchmark coverage are all solid and honest.
 */
export const HERO_STATS: HeroStat[] = [
  { symbol: "%", to: 450, decimals: 0, suffix: "/s", label: "Events ingested per second" },
  { symbol: "*", to: 1, decimals: 0, prefix: "O(", suffix: ")", label: "Model update cost" },
  { symbol: "<", to: 60, decimals: 0, suffix: "s", label: "Detection SLO" },
  { symbol: "#", to: 28, decimals: 0, suffix: "", label: "Benchmark entities" },
];

export interface LoopStep {
  index: string;
  title: string;
  body: string;
}

export const LOOP_STEPS: LoopStep[] = [
  {
    index: "01",
    title: "Ingest",
    body: "Prometheus scrapes CPU, memory, latency and error rates from every pod every 15 seconds.",
  },
  {
    index: "02",
    title: "Predict",
    body: "A HalfSpaceTrees model per service updates on every single event and emits an anomaly score. No batch retraining.",
  },
  {
    index: "03",
    title: "Decide",
    body: "A policy engine maps the score to a remediation level, then walks the dependency graph to find who else is at risk.",
  },
  {
    index: "04",
    title: "Act",
    body: "Every fix is a Kubernetes API call or a YARP traffic weight change. No restart scripts, no SSH.",
  },
];

export interface AnalogyRow {
  real: string;
  analogy: string;
}

/** The plain-English framing from docs/README.md. */
export const ANALOGY_ROWS: AnalogyRow[] = [
  { real: "Your microservices", analogy: "Patients" },
  { real: "Prometheus metrics", analogy: "The heart rate monitor" },
  { real: "Anomaly detection", analogy: "A doctor spotting abnormal signs" },
  { real: "Decision engine", analogy: "The emergency protocol" },
  { real: "Adaptive learning", analogy: "A doctor learning from past cases" },
  { real: "This dashboard", analogy: "The control room" },
];

export interface LadderRung {
  severity: Severity;
  range: string;
  action: string;
}

export const LADDER: LadderRung[] = [
  { severity: "watch", range: "< 0.50", action: "Log it and keep watching" },
  { severity: "warn", range: "0.50 - 0.70", action: "Alert, and pre warm a spare replica" },
  { severity: "degrade", range: "0.70 - 0.85", action: "Circuit break, shift half the traffic away, scale up" },
  { severity: "critical", range: "> 0.85", action: "Drain traffic to zero, restart the pod, roll the model back" },
];

export interface ResearchComponent {
  number: string;
  name: string;
  status: "Complete" | "In progress" | "Planned";
  body: string;
}

/** Status reflects the repo honestly: only Component 1 is actually done. */
export const RESEARCH_COMPONENTS: ResearchComponent[] = [
  {
    number: "01",
    name: "Anomaly detection",
    status: "Complete",
    body: "Online HalfSpaceTrees scoring, tuned and evaluated against the SMD benchmark.",
  },
  {
    number: "02",
    name: "Dynamic model updating",
    status: "In progress",
    body: "ADWIN drift detection with automatic rollback to the last stable snapshot.",
  },
  {
    number: "03",
    name: "Rule based decision engine",
    status: "In progress",
    body: "Dependency aware policy evaluation and graduated action dispatch.",
  },
  {
    number: "04",
    name: "Adaptive learning",
    status: "Planned",
    body: "Reinforcement learning over remediation outcomes to improve the policy.",
  },
  {
    number: "05",
    name: "LLM copilot",
    status: "Planned",
    body: "Retrieval augmented root cause analysis and post mortem drafting.",
  },
];

export interface StackItem {
  layer: string;
  tech: string;
  why: string;
}

/** The architecture layers, top (closest to the request) to bottom (runtime). */
export const STACK: StackItem[] = [
  { layer: "Observability UX", tech: "React, TypeScript", why: "Real time dashboards over a WebSocket stream." },
  { layer: "Traffic control", tech: "YARP", why: "Runtime reconfigurable proxy, so traffic shifts need no redeploy." },
  { layer: "Streaming ML", tech: "Python, FastAPI, river", why: "Best in class online learning libraries." },
  { layer: "Orchestration", tech: "C#, .NET 8", why: "Strong stateful background services and typed policy code." },
  { layer: "Model registry", tech: "MLflow", why: "Versioned runs make rollback a first class operation." },
  { layer: "Runtime", tech: "Kubernetes", why: "Every remediation is an ordinary API call against the cluster." },
];

export interface MarqueeItem {
  label: string;
  icon?: SimpleIcon;
}

/**
 * "Built on" strip -- what SHARP actually runs on, not fake customer logos.
 * Logos come from simple-icons. river and YARP are left text-only rather
 * than given a fake/generic icon -- river is a niche Python library and YARP
 * is an internal Microsoft project, neither has a real brand mark anywhere.
 */
export const MARQUEE_ITEMS: MarqueeItem[] = [
  { label: "Kubernetes", icon: siKubernetes },
  { label: "Prometheus", icon: siPrometheus },
  { label: "Redis", icon: siRedis },
  { label: "MLflow", icon: siMlflow },
  { label: "river" },
  { label: ".NET 8", icon: siDotnet },
  { label: "YARP" },
  { label: "TimescaleDB", icon: siTimescale },
  { label: "React", icon: siReact },
];

export interface FeatureCard {
  title: string;
  icon: LucideIcon;
  body: string;
}

/**
 * Icons are reused from the app's own nav/action iconography where the
 * concept overlaps (GitBranch is the dependency graph nav icon, Route is the
 * shift-traffic action icon on the services detail panel, Bot is the copilot
 * nav icon) rather than picked arbitrarily, so the marketing page's visual
 * language matches the real product's.
 */
export const FEATURE_GRID: FeatureCard[] = [
  {
    title: "Online learning",
    icon: Activity,
    body: "Every Prometheus scrape updates the model in place. No batch retrain job, no stale window.",
  },
  {
    title: "Graduated remediation",
    icon: SlidersHorizontal,
    body: "Four severity tiers, each with its own response, from a log line up to a full rollback.",
  },
  {
    title: "Dependency aware",
    icon: GitBranch,
    body: "A service going critical elevates its upstreams and pre-scales its downstreams automatically.",
  },
  {
    title: "Zero downtime traffic shifts",
    icon: Route,
    body: "YARP drains a failing pod to 0% weight instead of killing it, so in-flight requests finish.",
  },
  {
    title: "Versioned models",
    icon: History,
    body: "Every run is tracked in MLflow. Rollback to the last stable snapshot is one click, or automatic.",
  },
  {
    title: "Copilot for root cause",
    icon: Bot,
    body: "Ask what happened in plain English. RAG over incident history and telemetry summaries.",
  },
];

export interface RolloutPillar {
  label: string;
  icon: LucideIcon;
  items: string[];
  /** Absolute position within the desktop staircase, as a percentage of the
   *  container's own box -- not viewport units, so it stays scoped to this
   *  page's max-w-6xl column instead of the raw browser width. */
  leftPct: number;
  bottomPct: number;
}

/**
 * The adoption path, not the runtime loop -- LOOP_STEPS (Ingest/Predict/
 * Decide/Act) already covers what SHARP does once it's running; this is
 * about how a team actually gets it there.
 */
export const ROLLOUT_PILLARS: RolloutPillar[] = [
  { label: "Scope", icon: Search, items: ["services", "thresholds", "SLOs", "timeline"], leftPct: 3, bottomPct: 20 },
  {
    label: "Integrate",
    icon: Plug,
    items: ["Prometheus", "Redis", "MLflow", "Kubernetes API"],
    leftPct: 27,
    bottomPct: 27,
  },
  {
    label: "Certify",
    icon: ShieldCheck,
    items: ["dry-run mode", "chaos test", "policy check", "sign-off"],
    leftPct: 51,
    bottomPct: 34,
  },
  {
    label: "Activate",
    icon: Rocket,
    items: ["runbooks", "on-call handoff", "SLA tracking", "go-live"],
    leftPct: 75,
    bottomPct: 41,
  },
];

export interface IntegrationItem {
  label: string;
}

export const INTEGRATION_ITEMS: IntegrationItem[] = [
  { label: "Kubernetes API" },
  { label: "Prometheus" },
  { label: "Redis Streams" },
  { label: "MLflow" },
  { label: "TimescaleDB" },
  { label: "YARP" },
];
