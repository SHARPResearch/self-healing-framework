from sweep_hyperparams import build_grid


def test_build_grid_has_baseline_and_one_at_a_time_variants():
    grid = build_grid()

    assert len(grid) == 7
    baseline = grid[0]
    n_trees_variants = [c.n_trees for c in grid[1:3]]
    height_variants = [c.height for c in grid[3:5]]
    window_variants = [c.window_size for c in grid[5:7]]

    assert baseline.n_trees != 0
    assert n_trees_variants != [baseline.n_trees, baseline.n_trees]
    assert height_variants != [baseline.height, baseline.height]
    assert window_variants != [baseline.window_size, baseline.window_size]

    # every non baseline combo changes exactly one field vs baseline
    for cfg in grid[1:]:
        changed = sum([
            cfg.n_trees != baseline.n_trees,
            cfg.height != baseline.height,
            cfg.window_size != baseline.window_size,
        ])
        assert changed == 1
