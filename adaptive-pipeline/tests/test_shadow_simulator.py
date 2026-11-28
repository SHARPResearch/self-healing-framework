"""
test_shadow_simulator.py
Tests to prove our Imagination Engine provides sensible fallback estimates.
"""
import pytest
from app.shadow_simulator import ShadowSimulator
from app.dueling_dqn import RecoveryAction

def test_simulator_returns_positive_drop_for_recovery_actions():
    """Recovery actions should simulate a positive anomaly drop."""
    simulator = ShadowSimulator()
    drop = simulator.estimate_anomaly_drop(RecoveryAction.RESTART_POD)
    assert drop == 0.40, "RESTART_POD should simulate a 0.40 drop"

def test_simulator_returns_zero_for_no_action():
    """NO_ACTION should simulate a 0.0 drop."""
    simulator = ShadowSimulator()
    drop = simulator.estimate_anomaly_drop(RecoveryAction.NO_ACTION)
    assert drop == 0.00, "NO_ACTION should simulate a 0.00 drop"

def test_simulator_detects_cold_start_regression():
    """Restarting a pod when the system is already healthy should flag a regression."""
    simulator = ShadowSimulator()
    # System is healthy (score 0.05), but we try to restart
    is_regression = simulator.is_simulated_regression(RecoveryAction.RESTART_POD, current_score=0.05)
    assert is_regression is True, "Should flag regression for restarting a healthy pod"