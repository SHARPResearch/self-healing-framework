# 0012. Show the raw telemetry on the lifecycle page; link to Grafana instead of embedding it

Date: 2026-11-21. Status: Accepted.

## Context
With Prometheus and Grafana in the cluster, the question was whether to bring them into the React
dashboard. The practitioners who evaluated the lifecycle page said that seeing the exact
statistical evidence is what makes automated model updates trustworthy. The page showed the
derived anomaly score and the decision's statistics, but not the telemetry the detector actually
scored, so an operator answering "new normal or incident?" could not check what had changed.

## Decision
In live mode the Model lifecycle page has a Telemetry evidence panel. For a chosen service and
window (30 min to 3 h) it shows the eight raw Prometheus features as small multiples, one axis
each in the feature's own unit, with the service's quarantines, change events and decisions drawn
as vertical rules and listed below. The backend serves it (`GET /api/live/{service}/telemetry`),
so the browser needs no access to Prometheus. A link opens the full Grafana dashboard for the
same service.

## Alternatives considered
- **Embed Grafana panels in iframes.** Rejected: it needs anonymous access and `allow_embedding`
  in Grafana and another origin in the browser, and its charts know nothing of lifecycle events.
  It would repeat Grafana inside the dashboard without adding evidence.
- **Query Prometheus from the browser.** Rejected: it exposes Prometheus to every dashboard user
  and duplicates the PromQL in `app/prom.py`, the one definition of what the detector sees.

## Consequences
The panel and the detector read the same queries, so what the operator sees is what was scored.
Lifecycle markers are kept in memory (the last 200 per service) and are lost on a backend
restart; the decision log keeps the full history. Replay mode has no panel: its telemetry is SMD,
already shown by the score chart.
