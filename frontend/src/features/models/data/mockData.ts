import type { ModelParams, ModelRun } from "../types";

/**
 * Mock only. Hyperparameters are the real Doc1 §4 defaults, and the eval
 * metrics are seeded from ml-pipeline/RESULTS.md's actual measured numbers
 * for the tuned entity (precision 0.4344, recall 0.8129, F1 0.5663).
 *
 * The per-service spread is deliberate, not decorative: RESULTS.md found the
 * tuned entity's F1 (0.5663) is nearly 5x the 28-entity mean (0.1195), because
 * HST score distributions differ enough per entity that one global threshold
 * does not transfer. Showing every service at the tuned best would misrepresent
 * the finding that motivates ml-pipeline/calibrate.py.
 */
const DEFAULT_PARAMS: ModelParams = {
  nTrees: 25,
  height: 15,
  windowSize: 250,
  seed: 42,
  adwinDelta: 0.002,
};

export const modelRuns: ModelRun[] = [
  {
    runId: "a3f1c9d24e8b41f0",
    entityId: "service-a-auth",
    serviceName: "Auth Service",
    version: 7,
    stage: "STREAMING",
    modelType: "HalfSpaceTrees",
    driftLibrary: "ADWIN",
    updatedAt: "2026-08-16T05:58:00Z",
    params: DEFAULT_PARAMS,
    metrics: {
      rollingMeanScore: 0.12,
      cumulativeDriftCount: 0,
      warnRate: 0.02,
      warmUpEvents: 28479,
      warmUpThroughputEps: 451,
      evalPrecision: 0.4344,
      evalRecall: 0.8129,
      evalF1: 0.5663,
    },
  },
  {
    runId: "b71d0e5a9c3f4827",
    entityId: "service-b-orders",
    serviceName: "Orders Service",
    version: 5,
    stage: "STREAMING",
    modelType: "HalfSpaceTrees",
    driftLibrary: "ADWIN",
    updatedAt: "2026-08-16T05:42:00Z",
    params: DEFAULT_PARAMS,
    metrics: {
      rollingMeanScore: 0.78,
      cumulativeDriftCount: 2,
      warnRate: 0.31,
      warmUpEvents: 24310,
      warmUpThroughputEps: 438,
      evalPrecision: 0.2105,
      evalRecall: 0.6642,
      evalF1: 0.3197,
    },
  },
  {
    runId: "c02a8b6f1d7e4390",
    entityId: "service-c-inventory",
    serviceName: "Inventory Service",
    version: 9,
    stage: "STREAMING",
    modelType: "HalfSpaceTrees",
    driftLibrary: "ADWIN",
    updatedAt: "2026-08-16T04:10:00Z",
    params: { ...DEFAULT_PARAMS, windowSize: 500 },
    metrics: {
      rollingMeanScore: 0.58,
      cumulativeDriftCount: 4,
      warnRate: 0.24,
      warmUpEvents: 31002,
      warmUpThroughputEps: 462,
      evalPrecision: 0.1544,
      evalRecall: 0.5218,
      evalF1: 0.2383,
    },
  },
  {
    runId: "d59e3c7a0b2f486d",
    entityId: "service-d-notification",
    serviceName: "Notification Service",
    version: 3,
    stage: "STREAMING",
    modelType: "HalfSpaceTrees",
    driftLibrary: "ADWIN",
    updatedAt: "2026-08-16T05:55:00Z",
    params: DEFAULT_PARAMS,
    metrics: {
      rollingMeanScore: 0.08,
      cumulativeDriftCount: 0,
      warnRate: 0.01,
      warmUpEvents: 19874,
      warmUpThroughputEps: 447,
      evalPrecision: 0.0912,
      evalRecall: 0.4477,
      evalF1: 0.1515,
    },
  },
  {
    runId: "e14f7d2b8a05c936",
    entityId: "service-e-payments",
    serviceName: "Payments Service",
    version: 12,
    stage: "STREAMING",
    modelType: "HalfSpaceTrees",
    driftLibrary: "ADWIN",
    updatedAt: "2026-08-16T06:05:00Z",
    params: { ...DEFAULT_PARAMS, nTrees: 50 },
    metrics: {
      rollingMeanScore: 0.91,
      cumulativeDriftCount: 6,
      warnRate: 0.48,
      warmUpEvents: 33518,
      warmUpThroughputEps: 402,
      evalPrecision: 0.1187,
      evalRecall: 0.7033,
      evalF1: 0.2031,
    },
  },
  {
    runId: "f8306ba4c1d29e57",
    entityId: "service-f-search",
    serviceName: "Search Service",
    version: 4,
    stage: "WARM_UP",
    modelType: "HalfSpaceTrees",
    driftLibrary: "ADWIN",
    updatedAt: "2026-08-16T05:50:00Z",
    params: DEFAULT_PARAMS,
    metrics: {
      rollingMeanScore: 0.15,
      cumulativeDriftCount: 0,
      warnRate: 0.03,
      warmUpEvents: 12240,
      warmUpThroughputEps: 455,
      evalPrecision: 0,
      evalRecall: 0,
      evalF1: 0,
    },
  },
];

/** Matches RESULTS.md's reported 28-entity mean, for the honest-spread callout. */
export const CROSS_ENTITY_MEAN_F1 = 0.1195;
export const TUNED_ENTITY_F1 = 0.5663;
