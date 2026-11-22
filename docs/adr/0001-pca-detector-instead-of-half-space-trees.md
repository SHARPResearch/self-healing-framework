# 0001. Smoothed PCA with a POT threshold instead of Half-Space Trees

Date: 2026-10-18. Status: Accepted.

## Context
The proposal used river's Half-Space Trees (HST) with one global percentile threshold. On SMD it
scored poorly on held-out servers, a threshold tuned on one machine was about 5x worse on the
others, and a shipped model was 368 MB.

## Decision
Use PCA reconstruction error on robustly scaled metrics (95% variance kept), smoothed by an EWMA
over 5 events, with a per-version threshold from Peaks-Over-Threshold at risk 0.01
(`detector_config("pca_s5")`, `threshold_method="pot"`).

## Alternatives considered
HST with robust z-scores, HST and PCA ensembles, longer smoothing, temporal-deviation features.
All were measured on the 8 development servers and lost (`ml-pipeline/RESULTS.md`).

## Consequences
Held-out PR-AUC +51% (p = 0.009), 34 KB per service. PCA reacts to any change in how metrics move
together, so it needs a lifecycle (0002) after deployments. PCA is degenerate on single-metric
series, so NAB keeps HST.
