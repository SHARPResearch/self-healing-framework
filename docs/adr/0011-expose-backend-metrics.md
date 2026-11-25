# 0011. Expose the backend's own metrics to Prometheus

Date: 2026-11-21. Status: Accepted.

## Context
Prometheus scraped Online Boutique, but not SHARP itself. Whether the scorer was keeping up,
reaching Prometheus or making decisions was visible only on our own dashboard. Two proposal
requirements, FR6 (at most 5 ms added per event) and FR4 (every transition logged), were measured
in an offline benchmark only.

## Decision
`GET /metrics` (`services/ml-backend/app/metrics.py`, `prometheus-client`) exposes:
- per service: events scored, alarming events, the latest score, alarm and post-restart flags,
  the model version, the lifecycle phase and the quarantine progress;
- counters of quarantines by trigger, decisions by verdict and action, model transitions, change
  events by kind and operator queries by outcome;
- histograms of the per-event scoring time (`sharp_score_seconds`, buckets from 25 µs to 250 ms
  around the 5 ms bound) and of each live Prometheus read.

The Helm chart adds a ServiceMonitor with `honorLabels: true`, so our `service` label (the
monitored Deployment) is kept instead of being renamed `exported_service` in favour of the scrape
target's own. A Grafana dashboard, "SHARP ml-backend: detection and CADAL lifecycle", ships as a
ConfigMap that the Grafana sidecar loads.

## Alternatives considered
- **Derive everything from the decision log in TimescaleDB.** Rejected: it gives no latency
  histogram, and it ties monitoring to the database being up.
- **OpenTelemetry metrics.** Rejected for now: the cluster already runs Prometheus and nothing
  else consumes OTLP. The metric names would carry over.

## Consequences
Label values are bounded (about ten services; fixed verdict, action, trigger and kind
vocabularies). The registry is private to the module, so tests and reloads cannot collide on
names. FR6 now has a production measurement next to the benchmark.
