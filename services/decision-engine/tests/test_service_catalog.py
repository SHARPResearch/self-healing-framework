from app.integration import catalog


def test_catalog_for_anomaly_synthesizes_live_service(monkeypatch):
    monkeypatch.setattr(catalog, "resolve_catalog", lambda: {})

    entry = catalog.catalog_for_anomaly(
        {
            "service_id": "adservice",
            "service_name": "Ad Service",
            "layer": "domain",
        }
    )["adservice"]

    assert entry["namespace"] == "online-boutique"
    assert entry["display_name"] == "Ad Service"
    assert entry["criticality"] == 0.5
    assert entry["runtime"] == "online-boutique"


def test_catalog_for_anomaly_keeps_known_service(monkeypatch):
    monkeypatch.setattr(
        catalog,
        "resolve_catalog",
        lambda: {"frontend": {"service_id": "frontend", "team": "web"}},
    )

    result = catalog.catalog_for_anomaly({"service_id": "frontend"})

    assert result["frontend"]["team"] == "web"
