# Adaptive Learning Decision Engine (RL)

**Component 3** of the Self-Healing AI-Driven Failure Prediction and Automated Recovery Framework.  
**Developer:** A.G.L.M Wijesinghe (IT23264670)  
**Status:** PP1 

## 🎯 Component Overview
This component serves as the intelligent "brain" of the self-healing framework. Unlike reactive systems (e.g., Kubernetes restarts), this engine uses **Reinforcement Learning (Deep Q-Networks)** to continuously learn and optimize microservice recovery actions (e.g., Restart, Scale Out, Route Traffic) while guaranteeing operational safety via Shadow Mode and Hybrid Arbitration.

## 🏗️ Architecture & Data Flow
1. **Input:** Receives an `EnrichedContextPayload` (JSON) from the Rule-Based Decision Engine (Component 2), containing real-time Prometheus metrics and dependency graph context.
2. **Processing (State Assembly):** Validates the payload via Pydantic (`schema.py`) and converts categorical/text data into a normalized 7-dimensional NumPy state vector (`state_assembler.py`).
3. **Processing (Policy Inference):** Passes the state vector through a Deep Q-Network (`dqn_policy_engine.py`) to calculate Q-values for all possible actions.
4. **Output:** Returns the optimal `RecoveryAction` Enum and its confidence score (Q-Value) to the Hybrid Arbitration module for final safety validation.

## 📦 Dependencies
Ensure you have Python 3.11+ installed. Install required packages via:
```bash
pip install -r requirements.txt
# OR if using pyproject.toml:
pip install .