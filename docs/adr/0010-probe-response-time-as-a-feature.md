# 0010. Probe each service's response time and score it as an eighth feature

Date: 2026-11-21. Status: Accepted.

## Context
The live chaos campaign of 2026-10-21 (Component 2 results, §10) detected 11 of 12 faults. The
miss was the network delay on productcatalogservice: a pod whose packets are delayed by 200 ms
uses no more CPU, memory or bandwidth, and all seven live features were resource counters.
Online Boutique exports no request metrics of its own, so nothing could show it.

## Decision
A Prometheus blackbox exporter (`infrastructure/online-boutique/blackbox-values.yaml`, installed by
`up.ps1`) sends one real request to every service every 5 s, with the protocol its own readiness
probe uses: a gRPC health check for the nine gRPC services, `GET /_healthz` for the frontend and
a TCP connect for redis-cart. `probe_latency` (the one-minute mean of `probe_duration_seconds`,
labelled with the Deployment's `app`) is the eighth feature in `services/ml-backend/app/prom.py`.

Targets use fully qualified names (`*.online-boutique.svc.cluster.local`): the exporter's gRPC
resolver ignores the cluster DNS search domains, so a short name times out after 3 s.

## Alternatives considered
- **A service mesh (Istio, Linkerd) for request latency.** Rejected: it adds a sidecar to every
  pod, which changes the resource features the detector learned, and it would be the largest
  component in a laptop cluster.
- **The load generator's own latency statistics.** Rejected: Locust measures the frontend only,
  so a delayed backend service would show up as a frontend change, attributed to the wrong
  service.
- **Instrumenting Online Boutique.** Rejected: we do not own it, and the point of the live mode is
  monitoring an unmodified system.

## Consequences
- A delay on a service is now a direct feature shift on that service. A test reproduces it:
  `test_a_network_delay_alarms_through_the_probe_latency_alone`.
- The probe measures the path through the Service (kube-proxy), not only the pod, so a node-level
  network problem also shows. It adds one health check per service per 5 s, a negligible load.
- The feature set changed, so checkpoints of seven-feature fleets do not restore (they are matched
  on features, 0005) and those services warm up once more. Recorded campaigns without the column
  are still evaluated on the seven features they have.
- Without the exporter the feature is a constant 0, which the detector ignores.
