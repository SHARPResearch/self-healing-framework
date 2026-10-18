"""
hst_state.py — Component 2: structure-sharing sparse snapshots of a river HalfSpaceTrees model.

Why this exists: pickling the tuned HST (n_trees=25, height=15) produces a ~53-71 MB blob that
takes ~3.5 s to dump and ~5.5 s to load on the target i7-1165G7, and building a fresh HST's tree
structure takes ~16 s. Both make "roll back within one scoring cycle" (proposal FR3) and
"train a challenger model on recent data" impractical if done naively.

The observation that fixes it: river's HST tree *structure* is a pure function of
(seed, n_trees, height, sorted feature names, limits) and never changes after the first
learn_one(). The only learned state is the per-node l_mass / r_mass counters, the window counter,
the first-window flag, and (when wrapped in a Pipeline) the MinMaxScaler's running min/max.
Mass is only ever non-zero along root-to-leaf paths that recent events visited, so for real
telemetry a few hundred nodes out of ~1.6M carry mass. Capturing just those, addressed by their
heap index (root=1, left=2i, right=2i+1), gives a snapshot that is thousands of times smaller and
can be captured or applied in milliseconds onto any model with the same structure.

Works for river's HalfSpaceTrees and for src.lazy_hst.LazyHalfSpaceTrees (Component 1 v2), whose
nodes only exist where data has been: there, "zeroing" a model is dropping back to bare roots and
applying a snapshot re-creates exactly the nodes it names, with the same deterministic splits.

Correctness relies on one invariant of river's HST: every learn_one() increments l_mass on every
node along its path, and the window pivot copies l_mass into r_mass, so a node with zero mass on
both counters can never have a descendant with non-zero mass. That lets every traversal here
prune at the first all-zero node.
"""

import hashlib
import json
import pickle
import zlib
from dataclasses import dataclass, field
from typing import Any

from river import compose
from river.anomaly import HalfSpaceTrees

from src.lazy_hst import LazyHalfSpaceTrees


def _split(model: Any) -> tuple[Any, HalfSpaceTrees]:
    """
    Return (scaler_or_None, hst) for a bare HST, a Pipeline(scaler, HST), or a detector wrapping
    one of those in `hst_model` (src/ensemble.RankEnsembleDetector).
    """
    model = getattr(model, "hst_model", model)
    if isinstance(model, compose.Pipeline):
        steps = list(model.steps.values())
        return (steps[0] if len(steps) > 1 else None), steps[-1]
    return None, model


def _tree_free(model: Any) -> bool:
    """True for detectors with no HST inside (src/detectors.PCADetector, possibly smoothed)."""
    return getattr(model, "hst_model", model) is None


def _feature_owner(model: Any) -> Any:
    """The innermost wrapped detector, which owns the feature list."""
    while hasattr(model, "base"):
        model = model.base
    return model


def _iter_massive(root) -> list[tuple[int, Any]]:
    """(heap_index, node) for every node with non-zero mass, pruning all-zero subtrees."""
    out = []
    stack = [(1, root)]
    while stack:
        idx, node = stack.pop()
        if not (node.l_mass or node.r_mass):
            continue
        out.append((idx, node))
        children = getattr(node, "children", None)
        if children:
            for offset, child in enumerate(children):
                if child is not None:  # lazy trees: never-visited children do not exist
                    stack.append((2 * idx + offset, child))
    return out


def _node_at(hst, tree: int, heap_idx: int):
    """
    Walk from a tree's root to the node at heap_idx (bits after the leading 1 are left/right),
    creating it, with its deterministic split, if the model is lazy and has not visited it yet.
    """
    node = hst.trees[tree]
    if isinstance(hst, LazyHalfSpaceTrees):
        idx, path = 1, []
        for bit in bin(heap_idx)[3:]:
            right = bit == "1"
            child = hst._child(tree, node, idx, right, path, create=True)
            path.append((node, right))
            node, idx = child, 2 * idx + int(right)
        return node
    for bit in bin(heap_idx)[3:]:
        node = node.children[int(bit)]
    return node


def structure_fingerprint(model: Any) -> str:
    """
    Hash of everything that determines the HST tree structure.

    Two models with the same fingerprint have identical trees, so a snapshot from one can be
    applied to the other. Returns an "unbuilt" marker before the first learn_one(), because
    river only builds the trees once it sees the feature names.
    """
    if _tree_free(model):
        return model.fingerprint()
    _, hst = _split(model)
    if not hst.trees:
        return "unbuilt"
    if isinstance(hst, LazyHalfSpaceTrees):
        # Lazy splits are a pure function of these, no need to look at any node.
        payload = json.dumps({
            "kind": "lazy", "n_trees": hst.n_trees, "height": hst.height,
            "window_size": hst.window_size, "seed": hst.seed, "features": list(hst.features),
            "limits": {k: list(v) for k, v in sorted(hst.limits.items())},
            "default_limits": list(hst.default_limits),
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
    first_tree_splits = []
    stack = [hst.trees[0]]
    while stack and len(first_tree_splits) < 64:
        node = stack.pop()
        if hasattr(node, "feature"):
            first_tree_splits.append((node.feature, round(node.threshold, 10)))
            stack.extend(node.children)
    payload = json.dumps({
        "n_trees": hst.n_trees,
        "height": hst.height,
        "window_size": hst.window_size,
        "seed": hst.seed,
        "splits": first_tree_splits,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class HSTState:
    """Everything a HalfSpaceTrees model has learned, without its (shared) tree structure."""
    fingerprint: str
    counter: int
    first_window: bool
    masses: list[list[tuple[int, int, int]]]  # per tree: (heap_idx, l_mass, r_mass)
    scaler_bytes: bytes | None = None
    meta: dict = field(default_factory=dict)
    extra: dict | None = None  # wrapper state, e.g. the ensemble's deviation scorer + references

    @property
    def n_massive_nodes(self) -> int:
        return sum(len(t) for t in self.masses)

    def to_bytes(self) -> bytes:
        body = {
            "fingerprint": self.fingerprint,
            "counter": self.counter,
            "first_window": self.first_window,
            "masses": self.masses,
            "scaler": self.scaler_bytes.hex() if self.scaler_bytes is not None else None,
            "meta": self.meta,
            "extra": self.extra,
        }
        return zlib.compress(json.dumps(body).encode())

    @classmethod
    def from_bytes(cls, blob: bytes) -> "HSTState":
        body = json.loads(zlib.decompress(blob))
        return cls(
            fingerprint=body["fingerprint"],
            counter=body["counter"],
            first_window=body["first_window"],
            masses=[[tuple(e) for e in tree] for tree in body["masses"]],
            scaler_bytes=bytes.fromhex(body["scaler"]) if body["scaler"] is not None else None,
            meta=body.get("meta", {}),
            extra=body.get("extra"),
        )


def capture(model: Any, meta: dict | None = None) -> HSTState:
    """Snapshot the learned state of a built model in O(non-zero nodes)."""
    if _tree_free(model):
        return HSTState(fingerprint=structure_fingerprint(model), counter=0, first_window=False,
                        masses=[], meta=dict(meta or {}), extra=model.extra_state())
    scaler, hst = _split(model)
    if not hst.trees:
        raise ValueError("Cannot capture an unbuilt HalfSpaceTrees (call learn_one first).")
    masses = [
        [(idx, node.l_mass, node.r_mass) for idx, node in _iter_massive(tree)]
        for tree in hst.trees
    ]
    return HSTState(
        fingerprint=structure_fingerprint(model),
        counter=hst.counter,
        first_window=hst._first_window,
        masses=masses,
        scaler_bytes=pickle.dumps(scaler) if scaler is not None else None,
        meta=dict(meta or {}),
        extra=model.extra_state() if hasattr(model, "extra_state") else None,
    )


def _zero_masses(hst: HalfSpaceTrees) -> None:
    if isinstance(hst, LazyHalfSpaceTrees):
        hst.trees = [hst._make_node(t, 1, hst._root_region(), 0) for t in range(hst.n_trees)]
        return
    for tree in hst.trees:
        for _, node in _iter_massive(tree):
            node.l_mass = 0
            node.r_mass = 0


def apply(model: Any, state: HSTState) -> None:
    """
    Overwrite a built model's learned state with `state`, in place.

    The model must share the snapshot's tree structure (same fingerprint). Cost is
    O(non-zero nodes of the current state + of the snapshot), i.e. milliseconds.
    """
    fp = structure_fingerprint(model)
    if fp != state.fingerprint:
        raise ValueError(
            f"Structure mismatch: model {fp} vs snapshot {state.fingerprint}. "
            "Snapshots only apply to models built with the same seed/config/features."
        )
    if _tree_free(model):
        model.set_extra_state(state.extra)
        return
    scaler, hst = _split(model)
    _zero_masses(hst)
    for t, entries in enumerate(state.masses):
        for idx, l_mass, r_mass in sorted(entries):  # parents before children
            node = _node_at(hst, t, idx)
            node.l_mass = l_mass
            node.r_mass = r_mass
    hst.counter = state.counter
    hst._first_window = state.first_window
    if scaler is not None and state.scaler_bytes is not None:
        scaler.__dict__.update(pickle.loads(state.scaler_bytes).__dict__)
    if hasattr(model, "set_extra_state"):
        model.set_extra_state(state.extra)


def materialize(model: Any, feature_names: list[str]) -> None:
    """
    Build an unbuilt model's tree structure from feature names alone, leaving it untrained.

    river builds the trees inside the first learn_one(), so this feeds one all-zero row and then
    resets. Used when a replica or an MLflow pyfunc loads a snapshot without any telemetry yet.
    """
    if _tree_free(model):
        _feature_owner(model).features = list(feature_names)
        reset(model)
        return
    _, hst = _split(model)
    if isinstance(hst, LazyHalfSpaceTrees):
        hst._ensure_trees({name: 0.0 for name in feature_names})  # roots only, no learning
    elif not hst.trees:
        model.learn_one({name: 0.0 for name in feature_names})
    reset(model)


def feature_names(model: Any) -> list[str]:
    """
    Feature names a built model's trees were constructed from.

    Read from `limits` (a defaultdict that river fills for every feature of the first row while
    building) rather than from the split nodes: features that never became a split still shaped
    the structure through the random draws.
    """
    if _tree_free(model):
        return list(_feature_owner(model).features)
    _, hst = _split(model)
    if isinstance(hst, LazyHalfSpaceTrees):
        return list(hst.features)
    return sorted(hst.limits)


def reset(model: Any, keep_scaler: bool = False) -> None:
    """
    Forget everything learned but keep the (expensive to build) tree structure.

    Gives a fresh challenger model in milliseconds instead of the ~16 s a newly constructed
    HST spends building its trees on its first learn_one().

    keep_scaler=True keeps the MinMaxScaler's running min/max. Challengers want this: a scaler
    re-learned from a few hundred events has narrow ranges that keep widening afterwards, which
    moves every point to a different tree cell than the one its learned mass sits in.
    """
    if _tree_free(model):
        model.clear_extra()
        return
    scaler, hst = _split(model)
    _zero_masses(hst)
    hst.counter = 0
    hst._first_window = True
    if scaler is not None and not keep_scaler:
        scaler.__dict__.update(type(scaler)().__dict__)
    if hasattr(model, "clear_extra"):
        model.clear_extra()
