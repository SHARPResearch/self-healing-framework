# Architecture decision records: Component 2 (CADAL) and the anomaly detector

One file per decision, numbered in the order it was made. Each says what was decided, why, what
else was considered, and what it costs. A decision that is replaced is not deleted: its status says
which record superseded it.

Scope: `ml-pipeline/` (detector and lifecycle research code), `services/ml-backend/` (serving),
the lifecycle pages of `frontend/`, and the Online Boutique deployment in `infrastructure/`.

| # | Decision | Status |
|---|---|---|
| [0001](0001-pca-detector-instead-of-half-space-trees.md) | Smoothed PCA with a POT threshold instead of Half-Space Trees | Accepted |
| [0002](0002-attribute-before-acting.md) | Attribute a shift before acting, instead of rolling back on every drift | Accepted |
| [0003](0003-sequential-early-stop.md) | End a quarantine early only when the evidence is conclusive | Accepted |
| [0004](0004-staged-silent-demo.md) | Stage the silent-change demo so it is repeatable | Accepted (demo only) |
| [0005](0005-checkpoint-lifecycle-state.md) | Persist each service's lifecycle state and restore it on restart | Accepted |

Template:

```markdown
# NNNN. Title

Date: YYYY-MM-DD. Status: Proposed | Accepted | Superseded by NNNN.

## Context
## Decision
## Alternatives considered
## Consequences
```
