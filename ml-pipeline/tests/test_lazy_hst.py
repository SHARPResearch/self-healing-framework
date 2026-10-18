import random

from river.anomaly import HalfSpaceTrees
from river.anomaly.hst import HSTBranch, HSTLeaf

from src.lazy_hst import LazyHalfSpaceTrees


def _rows(n, seed=0, shift=0.0):
    rng = random.Random(seed)
    return [{"a": min(1.0, rng.random() * 0.5 + shift), "b": rng.random() * 0.3,
             "c": rng.betavariate(2, 5)} for _ in range(n)]


def _river_with_lazy_structure(lazy: LazyHalfSpaceTrees) -> HalfSpaceTrees:
    """A river HST whose (fully built) trees are exactly the lazy model's deterministic splits."""
    def build(tree, idx, lo, hi, depth):
        proto = lazy._make_node(tree, idx, (lo, hi), depth)
        if proto.feature is None:
            return HSTLeaf(l_mass=0, r_mass=0)
        i = proto.fidx
        left_hi, right_lo = hi[:], lo[:]
        left_hi[i], right_lo[i] = proto.threshold, proto.threshold
        left = build(tree, 2 * idx, lo[:], left_hi, depth + 1)
        right = build(tree, 2 * idx + 1, right_lo, hi[:], depth + 1)
        return HSTBranch(left, right, proto.feature, proto.threshold, l_mass=0, r_mass=0)

    river = HalfSpaceTrees(n_trees=lazy.n_trees, height=lazy.height, window_size=lazy.window_size)
    lo, hi = lazy._root_region()
    river.trees = [build(t, 1, lo[:], hi[:], 0) for t in range(lazy.n_trees)]
    river._tree_nodes = [list(t.iter_dfs()) for t in river.trees]
    return river


def test_same_algorithm_as_river_on_the_same_structure():
    lazy = LazyHalfSpaceTrees(n_trees=4, height=5, window_size=20, seed=3)
    lazy.learn_one(_rows(1)[0])  # fixes the feature set
    river = _river_with_lazy_structure(lazy)
    river.learn_one(_rows(1)[0])

    stream = _rows(150, seed=1) + _rows(150, seed=2, shift=0.4) + _rows(80, seed=3)
    for i, x in enumerate(stream):
        assert lazy.score_one(x) == river.score_one(x), f"score diverged at event {i}"
        lazy.learn_one(x)
        river.learn_one(x)
    probe = _rows(40, seed=9) + _rows(40, seed=10, shift=0.5)
    assert [lazy.score_one(x) for x in probe] == [river.score_one(x) for x in probe]


def test_structure_is_deterministic_across_instances_and_visit_order():
    a = LazyHalfSpaceTrees(n_trees=3, height=6, window_size=10, seed=5)
    b = LazyHalfSpaceTrees(n_trees=3, height=6, window_size=10, seed=5)
    for x in _rows(60, seed=1):
        a.learn_one(x)
    for x in _rows(60, seed=2, shift=0.3):  # different data, different nodes get created
        b.learn_one(x)
    # Wherever both have a node, it is the same split.
    stack = list(zip(a.trees, b.trees))
    compared = 0
    while stack:
        na, nb = stack.pop()
        assert (na.feature, na.threshold) == (nb.feature, nb.threshold)
        compared += 1
        for ca, cb in ((na.left, nb.left), (na.right, nb.right)):
            if ca is not None and cb is not None:
                stack.append((ca, cb))
    assert compared >= 3


def test_memory_scales_with_visited_cells_not_with_height():
    model = LazyHalfSpaceTrees(n_trees=25, height=15, window_size=250, seed=42)
    for x in _rows(2000):
        model.learn_one(x)
    full = 25 * (2 ** 16 - 1)
    assert model.n_nodes() < full / 50


def test_wider_limits_make_out_of_range_values_anomalous():
    narrow = LazyHalfSpaceTrees(n_trees=25, height=10, window_size=100, seed=1)
    wide = LazyHalfSpaceTrees(n_trees=25, height=10, window_size=100, seed=1,
                              default_limits=(-0.25, 1.25))
    train = [{"a": random.Random(i).uniform(0.4, 1.0)} for i in range(400)]
    for x in train:
        narrow.learn_one(x)
        wide.learn_one(x)
    edge, beyond, far = {"a": 1.0}, {"a": 1.2}, {"a": 5.0}
    # With [0, 1] limits every split threshold is below 1, so anything past the edge of the
    # training range lands in exactly the same cell as the edge itself: identical scores, a
    # runaway metric can never look worse than the largest normal value.
    assert narrow.score_one(beyond) == narrow.score_one(edge) == narrow.score_one(far)
    # With wider limits the out-of-range values reach cells the training data never filled.
    assert wide.score_one(beyond) > wide.score_one(edge)


def test_scores_zero_until_the_first_window_completes():
    model = LazyHalfSpaceTrees(n_trees=2, height=3, window_size=10, seed=0)
    assert model.score_one({"a": 0.5}) == 0
    for x in _rows(9):
        model.learn_one(x)
    assert model.score_one(_rows(1)[0]) == 0
    model.learn_one(_rows(1)[0])
    assert model.score_one(_rows(1)[0]) > 0
