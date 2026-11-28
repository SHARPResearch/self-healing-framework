"""
test_reward_logger.py
Tests to prove our Filing Cabinet correctly saves receipts for the LLM Copilot.
"""
import os
import json
from app.reward_logger import RewardLogger

def test_reward_logger_creates_json_file():
    """The logger should create a JSON file in the outputs directory."""
    logger = RewardLogger(log_dir="test_outputs")
    breakdown = {"action": "RESTART_POD", "final_reward": 0.35}
    
    logger.log_reward(breakdown, "payment-service")
    
    assert os.path.exists("test_outputs/reward_logs.json"), "Log file was not created"
    
    with open("test_outputs/reward_logs.json", 'r') as f:
        logs = json.load(f)
        
    assert len(logs) == 1
    assert logs[0]["service_id"] == "payment-service"
    
    # Cleanup
    os.remove("test_outputs/reward_logs.json")
    os.rmdir("test_outputs")