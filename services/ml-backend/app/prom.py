"""
prom.py — live telemetry for Online Boutique on Kubernetes, read from Prometheus.

Seven features per service, each fetched with ONE query for every service of the namespace:

  cpu_rate       cores used                rate(container_cpu_usage_seconds_total)
  memory_used    bytes                     container_memory_working_set_bytes
  network_rx     bytes/s received          rate(container_network_receive_bytes_total)
  network_tx     bytes/s sent              rate(container_network_transmit_bytes_total)
  cpu_throttled  share of CFS periods      rate(container_cpu_cfs_throttled_periods_total)
                 that were throttled         / rate(container_cpu_cfs_periods_total)
  restarts       container restarts, 5 min increase(kube_pod_container_status_restarts_total)
  ready_ratio    available / desired       kube_deployment_status_replicas_available
                 replicas                    / kube_deployment_spec_replicas

The cAdvisor and kube-state-metrics series are labelled by pod, not by service, so every query
maps the pod name "<deployment>-<replicaset hash>-<pod hash>" to an "app" label with label_replace
and sums by it. The names of the first four match fleet.CANONICAL, so the metric rows persisted to
TimescaleDB keep the same feature keys as in replay mode.

The client is blocking (httpx); the runtime calls it from a worker thread.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)   # one INFO line per scrape query otherwise

FEATURES = ("cpu_rate", "memory_used", "network_rx", "network_tx", "cpu_throttled", "restarts", "ready_ratio")
POD_TO_APP = r'"app", "$1", "pod", "^(.+)-[a-z0-9]+-[a-z0-9]+$"'
EXCLUDED = {"loadgenerator"}            # the traffic source, not a service under observation


def _by_app(expr: str) -> str:
    return f"sum by (app) (label_replace({expr}, {POD_TO_APP}))"


def feature_queries(namespace: str) -> dict[str, str]:
    ns = f'namespace="{namespace}"'
    ctr = f'{ns}, container!="", container!="POD"'
    return {
        "cpu_rate": _by_app(f"rate(container_cpu_usage_seconds_total{{{ctr}}}[1m])"),
        "memory_used": _by_app(f"container_memory_working_set_bytes{{{ctr}}}"),
        # network counters are per pod (one series per interface), not per container
        "network_rx": _by_app(f'rate(container_network_receive_bytes_total{{{ns}, interface="eth0"}}[1m])'),
        "network_tx": _by_app(f'rate(container_network_transmit_bytes_total{{{ns}, interface="eth0"}}[1m])'),
        "cpu_throttled": (
            f"({_by_app(f'rate(container_cpu_cfs_throttled_periods_total{{{ctr}}}[1m])')})"
            f" / clamp_min({_by_app(f'rate(container_cpu_cfs_periods_total{{{ctr}}}[1m])')}, 1e-9)"),
        "restarts": _by_app(f"increase(kube_pod_container_status_restarts_total{{{ns}}}[5m])"),
        "ready_ratio": (
            f'sum by (app) (label_replace(kube_deployment_status_replicas_available{{{ns}}}, "app", "$1", "deployment", "(.*)"))'
            f' / clamp_min(sum by (app) (label_replace(kube_deployment_spec_replicas{{{ns}}}, "app", "$1", "deployment", "(.*)")), 1)'),
    }


def services_query(namespace: str) -> str:
    return f'kube_deployment_spec_replicas{{namespace="{namespace}"}}'


@dataclass
class PrometheusClient:
    url: str
    timeout: float = 10.0

    def _get(self, path: str, params: dict) -> list:
        resp = httpx.get(f"{self.url.rstrip('/')}/api/v1/{path}", params=params, timeout=self.timeout)
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            raise RuntimeError(f"prometheus: {body.get('error', body)}")
        return body["data"]["result"]

    def query(self, promql: str) -> list:
        return self._get("query", {"query": promql})

    def query_range(self, promql: str, start: datetime, end: datetime, step_s: float) -> list:
        return self._get("query_range", {"query": promql, "start": start.timestamp(),
                                          "end": end.timestamp(), "step": step_s})  # seconds; "5.0s" is rejected

    def healthy(self) -> bool:
        try:
            return httpx.get(f"{self.url.rstrip('/')}/-/healthy", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False


def _value(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None   # drop NaN / inf


class OnlineBoutiqueTelemetry:
    """
    Per-service feature rows from Prometheus. Gaps (a series missing at one scrape, a 0/0 ratio)
    are forward-filled from the service's last row, and default to 0 before any value is seen, so
    the detector always gets the same fixed set of features.
    """

    def __init__(self, client: PrometheusClient, namespace: str):
        self.client = client
        self.namespace = namespace
        self.queries = feature_queries(namespace)
        self.last: dict[str, dict] = {}

    def services(self) -> list[str]:
        names = {r["metric"].get("deployment") for r in self.client.query(services_query(self.namespace))}
        return sorted(n for n in names if n and n not in EXCLUDED)

    def _fill(self, service: str, values: dict) -> dict:
        prev = self.last.get(service, {})
        row = {f: values[f] if values.get(f) is not None else prev.get(f, 0.0) for f in FEATURES}
        self.last[service] = row
        return row

    def latest(self, services: list[str]) -> dict[str, dict]:
        """One row per service at the current scrape."""
        values: dict[str, dict] = {s: {} for s in services}
        for feature, promql in self.queries.items():
            for r in self.client.query(promql):
                app = r["metric"].get("app")
                if app in values:
                    values[app][feature] = _value(r["value"][1])
        return {s: self._fill(s, values[s]) for s in services}

    def history(self, services: list[str], minutes: float, step_s: float) -> dict[str, list[dict]]:
        """Aligned per-service rows for the last `minutes`, oldest first (the warm-up data)."""
        end = datetime.now(timezone.utc)
        start = datetime.fromtimestamp(end.timestamp() - minutes * 60, timezone.utc)
        return {s: [r for _, r in rows] for s, rows in self.between(services, start, end, step_s).items()}

    def between(self, services: list[str], start: datetime, end: datetime,
                step_s: float) -> dict[str, list[tuple[float, dict]]]:
        """(unix time, row) per service between start and end, oldest first, gaps forward-filled."""
        grid: dict[str, dict[float, dict]] = {s: {} for s in services}
        for feature, promql in self.queries.items():
            for r in self.client.query_range(promql, start, end, step_s):
                app = r["metric"].get("app")
                if app not in grid:
                    continue
                for ts, v in r["values"]:
                    grid[app].setdefault(float(ts), {})[feature] = _value(v)
        out: dict[str, list[tuple[float, dict]]] = {}
        for s in services:
            self.last.pop(s, None)
            out[s] = [(ts, self._fill(s, grid[s][ts])) for ts in sorted(grid[s])]
        return out
