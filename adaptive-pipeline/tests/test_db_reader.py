def test_fetch_shadow_records_returns_rows():
    from app.db_reader import fetch_shadow_records
    records = fetch_shadow_records(limit=10)
    assert len(records) > 0, "shadow_records table should have data"
    assert "candidate_action" in records[0]
    assert "verdict" in records[0]

def test_fetch_decision_log_has_blast_factor():
    from app.db_reader import fetch_decision_log
    rows = fetch_decision_log(limit=10)
    assert len(rows) > 0
    assert "blast_factor" in rows[0]
    assert "centrality" in rows[0]