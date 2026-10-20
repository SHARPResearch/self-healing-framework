import type {
  LifecycleDecision,
  LifecyclePhase,
  ModelTransition,
  ModelVersionInfo,
  OperatorQuery,
} from "@/features/lifecycle/types";

/** Mirrors the MLflow run tags/params/metrics the pipeline actually logs. */
export type ModelStage = "WARM_UP" | "STREAMING" | "ARCHIVED";

export interface ModelParams {
  nTrees: number;
  height: number;
  windowSize: number;
  seed: number;
  adwinDelta: number;
}

export interface ModelMetrics {
  rollingMeanScore: number;
  cumulativeDriftCount: number;
  warnRate: number;
  warmUpEvents: number;
  warmUpThroughputEps: number;
  evalPrecision: number;
  evalRecall: number;
  evalF1: number;
}

export interface ModelRun {
  runId: string;
  entityId: string;
  serviceName: string;
  version: number;
  stage: ModelStage;
  modelType: "HalfSpaceTrees" | "PCA";
  driftLibrary: "ADWIN";
  updatedAt: string;
  params: ModelParams;
  metrics: ModelMetrics;
  // Present when served by services/ml-backend (the CADAL lifecycle), absent on mock runs.
  detector?: string;
  thresholdMethod?: string;
  phase?: LifecyclePhase;
  productionVersion?: number;
  versionCount?: number;
  rebaselined?: Record<string, number>;
  openQueries?: number;
  lastDecision?: LifecycleDecision | null;
}

export interface ModelDetail extends ModelRun {
  versions: ModelVersionInfo[];
  transitions: ModelTransition[];
  decisions: LifecycleDecision[];
  queries: OperatorQuery[];
}
