import pytest

from app import topology_ob


class FakePrometheus:
    def __init__(self, rows):
        self.rows = rows

    def query(self, promql):
        self.promql = promql
        return self.rows


def test_snapshot_filters_live_deployments_and_uses_catalog_edges():
    data = topology_ob.snapshot(live={"frontend", "adservice"})

    assert [node["id"] for node in data["nodes"]] == ["frontend", "adservice"]
    assert data["edge_source"] == "catalog"
    assert data["edges"] == [
        {
            "source": "frontend",
            "target": "adservice",
            "strength": 0.4,
            "protocol": "grpc",
        }
    ]


def test_snapshot_uses_istio_edges_when_prometheus_has_traffic():
    client = FakePrometheus(
        [
            {
                "metric": {
                    "source_workload": "frontend",
                    "destination_workload": "adservice",
                },
                "value": [0, "2.5"],
            }
        ]
    )

    data = topology_ob.snapshot(
        live={"frontend", "adservice"}, prom_client=client
    )

    assert data["edge_source"] == "istio"
    assert data["edges"][0]["source"] == "frontend"
    assert data["edges"][0]["target"] == "adservice"
    assert "istio_requests_total" in client.promql


def test_version_changes_with_health():
    first = topology_ob.snapshot(live={"frontend"})
    second = topology_ob.snapshot(
        live={"frontend"}, health={"frontend": "degraded"}
    )

    assert first["version"] != second["version"]
