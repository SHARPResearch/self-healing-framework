"""
lazy_hst.py — Component 1 v2: Half-Space Trees whose nodes exist only where data has been.

Same algorithm as river.anomaly.HalfSpaceTrees (Tan, Ting & Liu, IJCAI 2011; river's hst.py):
per-node l_mass / r_mass counters, a reference window that pivots every `window_size` learned
events, and the same mass-weighted score normalised to [0, 1]. What differs is *when* the trees
are built.

river builds every tree completely on the first learn_one(): 25 trees x 2^16 nodes = ~1.6M Python
objects, ~16 s and ~300-600 MB per model on the target laptop, for a model in which only a few
thousand nodes ever carry mass. Here a node is created the first time an event walks into it, and
its split is drawn from an RNG seeded by (seed, tree, heap index). The structure is therefore
still a pure function of the configuration: two instances with the same seed and features have
identical splits wherever both have nodes, on any machine, without building anything up front.
Nodes whose masses fall back to zero after a window pivot are dropped and re-created identically
if visited again. Memory and pivot cost scale with visited nodes, not with 2^height.

The splits are not bit-identical to river's (river draws them from one sequential RNG), so scores
differ in detail but follow the same distribution; compare_detectors.py checks accuracy on SMD.

Also supports wider feature limits (`default_limits`). Values outside the range seen in training
then fall into sparsely populated cells and score as anomalous, instead of landing in the edge
cell next to the largest normal value (a blind spot of HST with [0, 1] limits after min-max
scaling, see docs/Component_2_Dynamic_Model_Updating.md).
"""

from __future__ import annotations

import random

from river import anomaly

PADDING = 0.15  # same as river's make_padded_tree


class LazyNode:
    __slots__ = ("feature", "threshold", "l_mass", "r_mass", "left", "right")

    def __init__(self, feature, threshold):
        self.feature = feature        # None for a leaf
        self.threshold = threshold
        self.l_mass = 0
        self.r_mass = 0
        self.left: LazyNode | None = None
        self.right: LazyNode | None = None

    @property
    def children(self):
        return (self.left, self.right)


class LazyHalfSpaceTrees(anomaly.base.AnomalyDetector):
    def __init__(
        self,
        n_trees: int = 10,
        height: int = 8,
        window_size: int = 250,
        limits: dict | None = None,
        default_limits: tuple[float, float] = (0.0, 1.0),
        seed: int | None = None,
    ):
        self.n_trees = n_trees
        self.height = height
        self.window_size = window_size
        self.limits = dict(limits or {})
        self.default_limits = tuple(default_limits)
        self.seed = seed
        self.features: tuple | None = None
        self.trees: list[LazyNode] = []
        self.counter = 0
        self._first_window = True

    # ── structure ────────────────────────────────────────────────────────────
    def _limits_of(self, feature):
        return self.limits.get(feature, self.default_limits)

    def _rng(self, tree: int, heap_idx: int) -> random.Random:
        return random.Random(((self.seed or 0) * 1_000_003 + tree) * (1 << 24) + heap_idx)

    def _make_node(self, tree: int, heap_idx: int, region: dict, depth: int) -> LazyNode:
        if depth == self.height:
            return LazyNode(None, None)
        rng = self._rng(tree, heap_idx)
        feats = self.features
        feature = rng.choices(feats, weights=[region[f][1] - region[f][0] for f in feats])[0]
        a, b = region[feature]
        threshold = rng.uniform(a + PADDING * (b - a), b - PADDING * (b - a))
        return LazyNode(feature, threshold)

    def _region(self, path: list[tuple[LazyNode, int]]) -> dict:
        """Feature limits of the cell reached by following `path` (node, went_right) from the root."""
        region = {f: self._limits_of(f) for f in self.features}
        for node, right in path:
            lo, hi = region[node.feature]
            region[node.feature] = (node.threshold, hi) if right else (lo, node.threshold)
        return region

    def _child(self, tree: int, node: LazyNode, heap_idx: int, right: bool, path, create: bool):
        child = node.right if right else node.left
        if child is None and create:
            region = self._region(path + [(node, right)])
            child = self._make_node(tree, 2 * heap_idx + int(right), region, len(path) + 1)
            if right:
                node.right = child
            else:
                node.left = child
        return child

    def _ensure_trees(self, x: dict) -> None:
        if self.trees:
            return
        self.features = tuple(sorted(x))
        root_region = {f: self._limits_of(f) for f in self.features}
        self.trees = [self._make_node(t, 1, root_region, 0) for t in range(self.n_trees)]

    def _go_right(self, node: LazyNode, x: dict) -> bool:
        try:
            return x[node.feature] >= node.threshold
        except KeyError:  # missing feature: follow the most visited side, as river does
            left_mass = node.left.l_mass if node.left else 0
            right_mass = node.right.l_mass if node.right else 0
            return left_mass < right_mass

    # ── learning ─────────────────────────────────────────────────────────────
    def learn_one(self, x):
        self._ensure_trees(x)
        for t, root in enumerate(self.trees):
            node, idx, path = root, 1, []
            for _ in range(self.height):
                node.l_mass += 1
                right = self._go_right(node, x)
                child = self._child(t, node, idx, right, path, create=True)
                path.append((node, right))
                node, idx = child, 2 * idx + int(right)
            node.l_mass += 1

        self.counter += 1
        if self.counter == self.window_size:
            for root in self.trees:
                self._pivot(root)
            self._first_window = False
            self.counter = 0

    def _pivot(self, root: LazyNode) -> None:
        """r_mass <- l_mass, l_mass <- 0 on every existing node; drop subtrees left with no mass."""
        stack = [root]
        while stack:
            node = stack.pop()
            node.r_mass, node.l_mass = node.l_mass, 0
            for side in ("left", "right"):
                child = getattr(node, side)
                if child is None:
                    continue
                if child.l_mass == 0:  # will have zero mass on both counters after the pivot
                    setattr(node, side, None)
                else:
                    stack.append(child)

    # ── scoring ──────────────────────────────────────────────────────────────
    @property
    def size_limit(self):
        return 0.1 * self.window_size

    @property
    def _max_score(self):
        return self.n_trees * self.window_size * (2 ** (self.height + 1) - 1)

    def score_one(self, x):
        if self._first_window or not self.trees:
            return 0
        size_limit = self.size_limit
        total = 0.0
        for root in self.trees:
            node, depth_pow, score = root, 1, 0.0
            for _ in range(self.height):
                r = node.r_mass
                score += r * depth_pow
                if r < size_limit:
                    break
                child = node.right if self._go_right(node, x) else node.left
                if child is None:  # never-visited cell: zero mass, stop like river does
                    break
                node = child
                depth_pow <<= 1
            else:
                score += node.r_mass * depth_pow
            total += score
        return 1 - total / self._max_score

    # ── introspection ────────────────────────────────────────────────────────
    def n_nodes(self) -> int:
        count, stack = 0, list(self.trees)
        while stack:
            node = stack.pop()
            count += 1
            stack.extend(c for c in (node.left, node.right) if c is not None)
        return count
