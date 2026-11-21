"""
metrics.py — the backend's own Prometheus metrics, served at GET /metrics.

Two audiences:
- Operations: is the scorer up, keeping pace with its scrapes, and reaching Prometheus?
- The research claims, measured in production instead of only in a benchmark. Proposal FR6 (at
  most 5 ms added per event) is sharp_score_seconds. FR4 (every transition logged) is countable
  as sharp_model_transitions_total. The lifecycle outcomes (promote, hold, ask, resume) are
  sharp_lifecycle_decisions_total.

Labels are bounded: `service` is one of the monitored Deployments (about ten), the verdict,
action, transition, trigger and change kind come from fixed vocabularies in ml-pipeline.
The registry is a private one, so test runs and module reloads never collide on metric names.
"""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client import CONTENT_TYPE_LATEST  # noqa: F401 - re-exported for the route

REGISTRY = CollectorRegistry(auto_describe=True)

PHASES = ("stable", "quarantine", "deciding")

events_scored = Counter(
    "sharp_events_scored", "Telemetry events scored by the serving model", ["service"], registry=REGISTRY)
alarm_events = Counter(
    "sharp_alarm_events", "Scored events at or above the serving model's threshold", ["service"],
    registry=REGISTRY)
anomaly_score = Gauge(
    "sharp_anomaly_score", "Latest anomaly score, normalised so 0.5 is the calibrated threshold",
    ["service"], registry=REGISTRY)
alarm = Gauge("sharp_alarm", "1 while the latest event alarms", ["service"], registry=REGISTRY)
expected_alarm = Gauge(
    "sharp_alarm_after_restart", "1 while the service is inside its post-restart settling window "
    "(alarms there are labelled expected, docs/adr/0008)", ["service"], registry=REGISTRY)
model_version = Gauge(
    "sharp_model_version", "Production model version serving the service", ["service"], registry=REGISTRY)
phase = Gauge(
    "sharp_lifecycle_phase", "1 for the lifecycle phase the service is in", ["service", "phase"],
    registry=REGISTRY)
quarantine_progress = Gauge(
    "sharp_quarantine_progress_ratio", "Share of the open quarantine's evidence collected (0 when none)",
    ["service"], registry=REGISTRY)
decisions = Counter(
    "sharp_lifecycle_decisions", "Closed quarantines by attributed verdict and action",
    ["service", "verdict", "action"], registry=REGISTRY)
quarantines = Counter(
    "sharp_quarantines_opened", "Quarantines opened, by trigger", ["service", "trigger"], registry=REGISTRY)
transitions = Counter(
    "sharp_model_transitions", "Model registry transitions (register, promote, rollback, checkpoint)",
    ["service", "transition"], registry=REGISTRY)
changes = Counter(
    "sharp_change_events", "Change events that reached the lifecycle, by kind", ["service", "kind"],
    registry=REGISTRY)
queries = Counter(
    "sharp_operator_queries", "Operator queries by outcome (asked, new_normal, incident, expired)",
    ["service", "outcome"], registry=REGISTRY)

# Scoring one event is ~0.03 ms (p50) in the benchmark; the buckets resolve that and the 5 ms bound.
score_seconds = Histogram(
    "sharp_score_seconds", "Time to score one event and step its lifecycle (proposal FR6: <= 5 ms)",
    buckets=(2.5e-5, 5e-5, 1e-4, 2.5e-4, 5e-4, 1e-3, 2.5e-3, 5e-3, 1e-2, 5e-2, 0.25), registry=REGISTRY)
scrape_seconds = Histogram(
    "sharp_prometheus_scrape_seconds", "Live mode: time to read one scrape of every feature from Prometheus",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10), registry=REGISTRY)
scrape_failures = Counter(
    "sharp_prometheus_scrape_failures", "Live mode: scrapes that failed", registry=REGISTRY)
ready = Gauge("sharp_ready", "1 once the fleet is built and scoring", registry=REGISTRY)
services = Gauge("sharp_services", "Monitored services", registry=REGISTRY)


def observe_step(service: str, *, score: float, alarming: bool, after_restart: bool, version: int,
                 current_phase: str, progress: float) -> None:
    events_scored.labels(service).inc()
    if alarming:
        alarm_events.labels(service).inc()
    anomaly_score.labels(service).set(score)
    alarm.labels(service).set(1 if alarming else 0)
    expected_alarm.labels(service).set(1 if after_restart else 0)
    model_version.labels(service).set(version)
    for p in PHASES:
        phase.labels(service, p).set(1 if p == current_phase else 0)
    quarantine_progress.labels(service).set(progress)


def observe_lifecycle(service: str, event: str, data: dict) -> None:
    if event == "quarantine_opened":
        quarantines.labels(service, str(data.get("trigger") or "unknown")).inc()
    elif event == "lifecycle_decision":
        decisions.labels(service, str(data.get("verdict")), str(data.get("action"))).inc()
    elif event == "change_observed":
        changes.labels(service, str(data.get("kind") or "deployment")).inc()
    elif event == "operator_query":
        queries.labels(service, "asked").inc()
    elif event == "query_answered":
        queries.labels(service, str(data.get("answer") or "answered")).inc()
    elif event == "query_expired":
        queries.labels(service, "expired").inc()


def render() -> bytes:
    return generate_latest(REGISTRY)
