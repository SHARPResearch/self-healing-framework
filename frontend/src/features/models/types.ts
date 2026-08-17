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
  modelType: "HalfSpaceTrees";
  driftLibrary: "ADWIN";
  updatedAt: string;
  params: ModelParams;
  metrics: ModelMetrics;
}
