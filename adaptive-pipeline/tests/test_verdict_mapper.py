"""
test_verdict_mapper.py
Tests to prove our Translator correctly maps shadow verdicts to math.
"""
import pytest
from app.verdict_mapper import VerdictMapper

def test_mapper_converts_helped_verdict_to_positive():
    """A 'HELPED' verdict should yield a 1.0 multiplier."""
    mapper = VerdictMapper()
    assert mapper.get_multiplier("ACTION_WOULD_HAVE_HELPED") == 1.0

def test_mapper_converts_unnecessary_verdict_to_zero():
    """An 'UNNECESSARY' verdict should yield a 0.0 multiplier."""
    mapper = VerdictMapper()
    assert mapper.get_multiplier("ACTION_WOULD_HAVE_BEEN_UNNECESSARY") == 0.0

def test_mapper_converts_harmful_verdict_to_negative():
    """A 'HARMFUL' verdict should yield a -1.0 multiplier to punish the agent."""
    mapper = VerdictMapper()
    assert mapper.get_multiplier("HARMFUL") == -1.0

def test_mapper_handles_unknown_verdicts_safely():
    """Unknown or empty verdicts should default to 0.0 to prevent crashes."""
    mapper = VerdictMapper()
    assert mapper.get_multiplier("SOME_RANDOM_DB_ERROR") == 0.0
    assert mapper.get_multiplier(None) == 0.0