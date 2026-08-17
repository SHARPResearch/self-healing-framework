import type { Severity } from "@/shared/types";

/**
 * Third party asset, outside this repo's control. The hero renders a gradient
 * behind it so a dead URL degrades instead of showing black.
 */
export const HERO_VIDEO_URL =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260809_012548_ef22562c-c0ae-4816-ad9d-f8922af4e6a7.mp4";

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

export const STACK: StackItem[] = [
  { layer: "Streaming ML", tech: "Python, FastAPI, river", why: "Best in class online learning libraries." },
  { layer: "Orchestration", tech: "C#, .NET 8", why: "Strong stateful background services and typed policy code." },
  { layer: "Traffic control", tech: "YARP", why: "Runtime reconfigurable proxy, so traffic shifts need no redeploy." },
  { layer: "Observability UX", tech: "React, TypeScript", why: "Real time dashboards over a WebSocket stream." },
  { layer: "Model registry", tech: "MLflow", why: "Versioned runs make rollback a first class operation." },
  { layer: "Runtime", tech: "Kubernetes", why: "Every remediation is an ordinary API call against the cluster." },
];
