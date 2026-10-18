"""
The Rule Engine.

Input:  AnomalyContext
Output: list[RuleCandidate]  (sorted by priority DESC, then confidence DESC)

Pipeline per rule:
    1. Skip if rule disabled or context's service doesn't match applies_to
    2. Evaluate `when` condition tree against the context
    3. If matched, build a RuleCandidate with blended confidence
    4. Attach base_risk + blast_factor for downstream validation

Blended confidence per Component 2 spec:
    final = 0.6 * detection_confidence + 0.4 * rule_base_confidence

Condition evaluation is a safe AST walker — no eval(), no exec().

Supported operators:
    >  >=  <  <=  ==  !=  in  not_in  contains
"""
from __future__ import annotations

import logging
from typing import Any

from app.rules.context import AnomalyContext
from app.rules.models import (
    AllCondition,
    AnyCondition,
    ConditionOp,
    LeafCondition,
    Rule,
    RuleCandidate,
)
from app.rules.registry import rule_registry

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────
class RuleEngine:
    """Stateless. Reads rules from the singleton registry."""

    def evaluate(self, ctx: AnomalyContext) -> list[RuleCandidate]:
        """
        Return all matching candidates, sorted by priority DESC then
        final_confidence DESC.
        """
        detection_conf = float(ctx.anomaly.get("confidence", 0.8))
        matches: list[RuleCandidate] = []

        for rule in rule_registry.all():
            if not rule.enabled:
                continue

            # applies_to check
            layer = str(ctx.service.get("layer", ""))
            if not rule.applies_to.matches(layer, ctx.service_id):
                continue

            # condition evaluation
            try:
                matched = _eval_condition(rule.when, ctx)
            except Exception:
                log.exception("Rule %s: condition evaluation failed", rule.id)
                continue

            if not matched:
                continue

            cand = RuleCandidate(
                rule_id=rule.id,
                rule_version=rule.version,
                priority=rule.priority,
                action=rule.then.action,
                params=dict(rule.then.params),
                base_confidence=rule.then.base_confidence,
                detection_confidence=detection_conf,
                final_confidence=RuleCandidate.blend(
                    detection_conf, rule.then.base_confidence
                ),
                base_risk=rule.then.base_risk,
                blast_factor=ctx.blast_factor,
                centrality=ctx.centrality,
                guardrails=rule.guardrails,
            )
            matches.append(cand)

        matches.sort(key=lambda c: (-c.priority, -c.final_confidence))
        return matches

    def evaluate_best(self, ctx: AnomalyContext) -> RuleCandidate | None:
        """Convenience — return only the top candidate, or None."""
        all_matches = self.evaluate(ctx)
        return all_matches[0] if all_matches else None


# ─────────────────────────────────────────────────────────────────────
# Condition evaluation
# ─────────────────────────────────────────────────────────────────────
def _eval_condition(node: Any, ctx: AnomalyContext) -> bool:
    if isinstance(node, AllCondition):
        return all(_eval_condition(c, ctx) for c in node.all)
    if isinstance(node, AnyCondition):
        return any(_eval_condition(c, ctx) for c in node.any)
    if isinstance(node, LeafCondition):
        return _eval_leaf(node, ctx)
    # dict form (when loaded from JSONB, Pydantic normally wraps them,
    # but we handle raw dicts defensively)
    if isinstance(node, dict):
        if "all" in node:
            return all(_eval_condition(c, ctx) for c in node["all"])
        if "any" in node:
            return any(_eval_condition(c, ctx) for c in node["any"])
        if "metric" in node:
            return _eval_leaf(LeafCondition.model_validate(node), ctx)
    raise ValueError(f"Unknown condition node: {node!r}")


def _eval_leaf(leaf: LeafCondition, ctx: AnomalyContext) -> bool:
    actual = ctx.resolve(leaf.metric)
    expected = leaf.value
    op = leaf.op

    # Null handling: only "!=" and "not_in" survive a None actual
    if actual is None:
        if op == ConditionOp.NEQ:
            return True
        if op == ConditionOp.NOT_IN:
            return True
        return False

    try:
        if op == ConditionOp.GT:
            return actual > expected
        if op == ConditionOp.GTE:
            return actual >= expected
        if op == ConditionOp.LT:
            return actual < expected
        if op == ConditionOp.LTE:
            return actual <= expected
        if op == ConditionOp.EQ:
            return actual == expected
        if op == ConditionOp.NEQ:
            return actual != expected
        if op == ConditionOp.IN:
            return actual in expected
        if op == ConditionOp.NOT_IN:
            return actual not in expected
        if op == ConditionOp.CONTAINS:
            # both strings, or list-contains-scalar
            if isinstance(actual, (list, tuple, set)):
                return expected in actual
            return str(expected) in str(actual)
    except TypeError as e:
        log.warning(
            "Type mismatch in rule condition: metric=%s actual=%r expected=%r op=%s (%s)",
            leaf.metric, actual, expected, op, e,
        )
        return False

    raise ValueError(f"Unsupported op: {op}")


# ─────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────
rule_engine = RuleEngine()