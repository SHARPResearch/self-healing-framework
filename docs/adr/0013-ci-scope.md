# 0013. CI tests the components that serve the model, and builds the image they deploy

Date: 2026-11-21. Status: Accepted.

## Context
There was no CI: `.github/workflows/` was empty and every check ran on one laptop.

## Decision
`.github/workflows/ci.yml` runs on pull requests and on pushes to main:
- the `ml-pipeline` and `ml-backend` tests (173 and 34). The Server Machine Dataset they replay is
  downloaded once by the existing `datasets/smd/download.sh` and cached (`.github/actions/smd`).
  The backend tests use in-memory stores and a fake Prometheus, so no Docker or cluster is needed;
- the frontend typecheck and production build;
- `helm lint --strict`, and a render of the chart with the ServiceMonitor CRD available;
- the ml-backend image, built on every run and pushed on main only to
  `ghcr.io/<owner>/sharp-ml-backend`, tagged with the commit SHA. That tag is what
  `mlBackend.image.tag` takes.

## Alternatives considered
- **Deploy to a cluster from CI.** Rejected for now: there is no shared cluster, only minikube on a
  laptop. A pushed image and a chart that renders are what a deployment needs.
- **Run the full evaluations in CI.** Rejected: they take an hour or more and need the RCAEval and
  NAB data. They stay manual, and their outputs are committed.

## Consequences
CI covers the code paths CADAL and the detector run in, and the deployable artifact. The other
components' services have no jobs yet; their owners add them to the same workflow.
