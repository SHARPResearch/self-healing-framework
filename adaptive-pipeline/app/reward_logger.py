"""
reward_logger.py
The "Filing Cabinet" for Component 3.
Saves reward breakdowns to JSON for the LLM Copilot (Component 4) to read.
"""
import json
import os
from datetime import datetime , timezone

class RewardLogger:
    def __init__(self, log_dir: str = "outputs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, "reward_logs.json")

    def log_reward(self, breakdown: dict, service_id: str):
        """Appends a new reward breakdown to the JSON log file."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_id": service_id,
            "breakdown": breakdown
        }
        
        # Read existing logs or start a new list
        logs = []
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                logs = json.load(f)
                
        logs.append(entry)
        
        # Save back to file
        with open(self.log_file, 'w') as f:
            json.dump(logs, f, indent=4)