from train_all import discover_entities


def test_discover_entities_finds_all_28_smd_machines():
    entities = discover_entities()

    assert len(entities) == 28
    assert "machine-1-1" in entities
    assert "machine-3-11" in entities
    assert entities == sorted(entities)
