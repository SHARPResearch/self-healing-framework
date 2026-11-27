def test_settings_loads_without_secret():
    from app.config import settings
    assert settings.arbitration_mode in {"rule_only","hybrid","rl_preferred","rule_preferred"}
    assert 0.0 < settings.dqn_gamma < 1.0