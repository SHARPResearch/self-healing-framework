import type { ModelRun } from "../types";

const NOW_ISO = "2026-08-27T00:00:00Z";

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

/**
 * Mock "incremental update" a drift-alerted model runs: resolves drift,
 * promotes out of warm-up if applicable, and nudges metrics toward healthier
 * values by a fixed deterministic formula (not Math.random()), matching this
 * app's "no randomness in anything that renders" convention.
 */
export function applyModelUpdate(run: ModelRun): ModelRun {
  const wasWarmUp = run.stage === "WARM_UP";

  return {
    ...run,
    version: run.version + 1,
    stage: wasWarmUp ? "STREAMING" : run.stage,
    updatedAt: NOW_ISO,
    metrics: {
      ...run.metrics,
      cumulativeDriftCount: 0,
      rollingMeanScore: Number((run.metrics.rollingMeanScore * 0.4).toFixed(2)),
      warnRate: Number((run.metrics.warnRate * 0.4).toFixed(2)),
      evalF1: Number(
        (wasWarmUp ? 0.42 : clamp01(run.metrics.evalF1 + (1 - run.metrics.evalF1) * 0.15)).toFixed(4),
      ),
      evalPrecision: Number(
        (wasWarmUp ? 0.35 : clamp01(run.metrics.evalPrecision + (1 - run.metrics.evalPrecision) * 0.15)).toFixed(4),
      ),
      evalRecall: Number(
        (wasWarmUp ? 0.55 : clamp01(run.metrics.evalRecall + (1 - run.metrics.evalRecall) * 0.1)).toFixed(4),
      ),
    },
  };
}

/** Mock rollback to the previous version -- version step back, metrics untouched (rollback restores a known-good state, it doesn't degrade one). */
export function applyModelRollback(run: ModelRun): ModelRun {
  return {
    ...run,
    version: Math.max(1, run.version - 1),
    updatedAt: NOW_ISO,
  };
}
