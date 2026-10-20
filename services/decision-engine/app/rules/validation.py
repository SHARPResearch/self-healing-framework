"""
Rule payload validation — the dry-run behind POST /api/rules/{id}/validate.

Design principle: *fail safe*. Nothing here writes anything. It answers one
question: "would this rule be accepted by the engine, and would it ever
match anything we have seen recently?"

Checks performed:
    1. Pydantic parse — does the payload even describe a valid Rule?
    2. id slug shape
    3. applies_to layers are known layers, services are known (or "*")
    4. `when` is a structurally valid condition tree
    5. `then.action` is a valid ActionType
    6. id collision — only an error when creating a *new* rule
    7. (optional) match count against a sample of recent anomalies
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.rules.context import AnomalyContext
from app.rules.engine import _eval_condition
from app.rules.models import (
    ActionType,
    AllCondition,
    AnyCondition,
    ConditionNode,
    ConditionOp,
    LeafCondition,
    Rule,
)

log = logging.getLogger(__name__)

# ── Known vocabulary ────────────────────────────────────────────────
KNOWN_LAYERS: set[str] = {"edge", "bff", "domain", "data"}

# Metric namespaces the Context resolver understands. A metric that does
# not start with one of these will always resolve to None → the rule
# silently never fires. That is a warning, not an error (a future context
# builder may add namespaces).
KNOWN_METRIC_ROOTS: set[str] = {
    "anomaly",
    "service",
    "infra",
    "app",
    "graph",
    "blast_radius",
    "centrality",
    "classification",
}

VALID_OPS: set[str] = {op.value for op in ConditionOp}


# ─────────────────────────────────────────────────────────────────────
# Condition tree walker
# ─────────────────────────────────────────────────────────────────────
def _iter_leaf_conditions(node: Any) -> list[LeafCondition]:
    """Flatten a condition tree into its leaf comparisons.

    Accepts both Pydantic models and raw dicts (the validate endpoint is
    called with un-parsed JSON bodies).
    """
    leaves: list[LeafCondition] = []
    if isinstance(node, LeafCondition):
        leaves.append(node)
        return leaves
    if isinstance(node, (AllCondition, AnyCondition)):
        children = node.all if isinstance(node, AllCondition) else node.any
        for c in children:
            leaves.extend(_iter_leaf_conditions(c))
        return leaves
    if isinstance(node, dict):
        if "all" in node:
            for c in node["all"]:
                leaves.extend(_iter_leaf_conditions(c))
            return leaves
        if "any" in node:
            for c in node["any"]:
                leaves.extend(_iter_leaf_conditions(c))
            return leaves
        if "metric" in node:
            leaves.append(LeafCondition.model_validate(node))
            return leaves
    return leaves


def _validate_condition_tree(node: Any, errors: list[str], warnings: list[str]) -> bool:
    """
    Structural check of a condition tree. Returns True when the tree is
    well-formed. Mutates `errors` / `warnings`.
    """
    if isinstance(node, dict):
        if "all" in node or "any" in node:
            key = "all" if "all" in node else "any"
            children = node[key]
            if not isinstance(children, list) or len(children) == 0:
                errors.append(f"'{key}' group must contain at least one condition")
                return False
            ok = True
            for c in children:
                ok = _validate_condition_tree(c, errors, warnings) and ok
            return ok
        if "metric" in node:
            return _validate_leaf_dict(node, errors, warnings)
        errors.append(f"condition node must have 'all', 'any', or 'metric': {node!r}")
        return False

    if isinstance(node, AllCondition):
        if not node.all:
            errors.append("'all' group must contain at least one condition")
            return False
        return all(_validate_condition_tree(c, errors, warnings) for c in node.all)

    if isinstance(node, AnyCondition):
        if not node.any:
            errors.append("'any' group must contain at least one condition")
            return False
        return all(_validate_condition_tree(c, errors, warnings) for c in node.any)

    if isinstance(node, LeafCondition):
        _check_leaf(node, errors, warnings)
        return True

    errors.append(f"unknown condition node type: {type(node).__name__}")
    return False


def _validate_leaf_dict(d: dict, errors: list[str], warnings: list[str]) -> bool:
    metric = d.get("metric")
    op = d.get("op")
    if not isinstance(metric, str) or not metric:
        errors.append("leaf condition is missing a 'metric'")
        return False
    if op not in VALID_OPS:
        errors.append(
            f"leaf condition op {op!r} is not one of {sorted(VALID_OPS)}"
        )
        return False
    if "value" not in d:
        errors.append(f"leaf condition '{metric}' is missing a 'value'")
        return False
    if op in ("in", "not_in") and not isinstance(d["value"], list):
        errors.append(
            f"leaf condition '{metric}' uses op '{op}' — value must be a list"
        )
        return False
    _warn_metric_root(metric, warnings)
    return True


def _check_leaf(leaf: LeafCondition, errors: list[str], warnings: list[str]) -> None:
    if leaf.op in (ConditionOp.IN, ConditionOp.NOT_IN) and not isinstance(
        leaf.value, list
    ):
        errors.append(
            f"leaf condition '{leaf.metric}' uses op '{leaf.op.value}' — "
            "value must be a list"
        )
    _warn_metric_root(leaf.metric, warnings)


def _warn_metric_root(metric: str, warnings: list[str]) -> None:
    root = metric.partition(".")[0]
    if root not in KNOWN_METRIC_ROOTS:
        warnings.append(
            f"metric '{metric}' uses unknown namespace '{root}' — "
            "it will always resolve to null and the rule will never fire"
        )


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
def validate_rule_payload(
    payload: dict | Rule,
    *,
    existing_ids: set[str] | None = None,
    is_update: bool = False,
) -> dict[str, Any]:
    """
    Validate a rule payload WITHOUT saving it.

    Args:
        payload:      dict (raw JSON body) or an already-built Rule.
        existing_ids: ids currently in the DB — used for the collision check.
        is_update:    True when validating an edit of an existing rule, in
                      which case the rule reusing its own id is fine.

    Returns:
        {
          "valid": bool,
          "errors": [...],
          "warnings": [...],
          "rule": {...} | None        # the parsed rule, when valid
        }
    """
    errors: list[str] = []
    warnings: list[str] = []
    existing_ids = existing_ids or set()

    # ── 1. Pydantic parse ───────────────────────────────────────────
    rule: Rule | None = None
    if isinstance(payload, Rule):
        rule = payload
    else:
        try:
            rule = Rule.model_validate(payload)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err.get("loc", ()))
                errors.append(f"{loc}: {err.get('msg')}")
            return {"valid": False, "errors": errors, "warnings": warnings, "rule": None}

    # ── 2. id slug shape (model validator already ran, but re-assert) ─
    if not rule.id or not rule.id.replace("-", "").replace("_", "").isalnum():
        errors.append("id must be slug-like (a-z, 0-9, -, _)")

    # ── 3. id collision ─────────────────────────────────────────────
    if not is_update and rule.id in existing_ids:
        errors.append(
            f"rule id '{rule.id}' already exists — choose another id or "
            "edit the existing rule"
        )

    # ── 4. applies_to ───────────────────────────────────────────────
    unknown_layers = [l for l in rule.applies_to.layers if l not in KNOWN_LAYERS]
    if unknown_layers:
        errors.append(
            f"applies_to.layers contains unknown layers {unknown_layers} — "
            f"valid layers are {sorted(KNOWN_LAYERS)}"
        )
    overlap = set(rule.applies_to.services) & set(rule.applies_to.exclude_services)
    if overlap:
        warnings.append(
            f"services {sorted(overlap)} appear in both services and "
            "exclude_services — the exclusion wins"
        )

    # ── 5. condition tree ───────────────────────────────────────────
    _validate_condition_tree(rule.when, errors, warnings)

    # ── 6. action ───────────────────────────────────────────────────
    if not isinstance(rule.then.action, ActionType):
        errors.append(
            f"then.action '{rule.then.action}' is not a valid ActionType"
        )

    # ── 7. guardrails sanity ────────────────────────────────────────
    if rule.guardrails.max_per_hour < 1:
        errors.append("guardrails.max_per_hour must be >= 1")
    if rule.guardrails.cooldown_seconds < 0:
        errors.append("guardrails.cooldown_seconds must be >= 0")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "rule": rule.model_dump(mode="json") if not errors else None,
    }


def count_matches(
    rule: Rule,
    contexts: list[AnomalyContext],
) -> dict[str, Any]:
    """
    Dry-run a rule against a set of already-built contexts.

    Used by the builder's "Test Rule" button: "Would match N of M recent
    anomalies". Only contexts whose layer/service match `applies_to` are
    counted as eligible; the rest are skipped entirely.
    """
    matched: list[str] = []
    eligible = 0
    errored = 0

    for ctx in contexts:
        layer = str(ctx.service.get("layer", ""))
        if not rule.applies_to.matches(layer, ctx.service_id):
            continue
        eligible += 1
        try:
            if _eval_condition(rule.when, ctx):
                matched.append(ctx.anomaly.get("id") or ctx.service_id)
        except Exception:
            errored += 1

    total = len(contexts)
    return {
        "total_anomalies": total,
        "eligible_anomalies": eligible,
        "matched_count": len(matched),
        "matched_anomaly_ids": matched,
        "evaluation_errors": errored,
        "message": f"Would match {len(matched)} of {total} recent anomalies",
    }
