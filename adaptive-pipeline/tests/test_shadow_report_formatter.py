"""
test_shadow_report_formatter.py
Tests to prove our Shadow Report Formatter creates clean JSON for the LLM Copilot.
"""
from app.shadow_report_formatter import ShadowReportFormatter

def test_formatter_handles_empty_data():
    """If no shadow results are provided, it should return a safe default message."""
    formatter = ShadowReportFormatter()
    result = formatter.format_for_llm([])
    
    assert result["status"] == "no_shadow_data"
    assert "No shadow mode records found" in result["summary"]

def test_formatter_calculates_aggregate_metrics():
    """The formatter should correctly sum rewards and count helpful/harmful actions."""
    formatter = ShadowReportFormatter()
    mock_results = [
        {"counterfactual_reward": 0.5}, # Helpful
        {"counterfactual_reward": -1.0}, # Harmful
        {"counterfactual_reward": 0.2}  # Helpful
    ]
    
    result = formatter.format_for_llm(mock_results)
    
    assert result["total_records_analyzed"] == 3
    assert result["aggregate_metrics"]["total_counterfactual_reward"] == -0.3
    assert result["aggregate_metrics"]["helpful_actions_count"] == 2
    assert result["aggregate_metrics"]["harmful_actions_count"] == 1
    assert "Analyzed 3 shadow actions" in result["llm_summary_prompt"]