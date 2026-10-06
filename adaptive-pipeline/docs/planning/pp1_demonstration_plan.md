# PP1 Demonstration Plan - Adaptive Learning Decision Engine

## Student: A.G.L.M Wijesinghe (IT23264670)
## Presentation Date: October 21, 2026

---

## 1. Component Overview

**What is my component?**
The Adaptive Learning Decision Engine using Reinforcement Learning (RL) that optimizes microservice recovery actions through continuous learning.

**Why is it necessary?**
- Current solutions (Kubernetes) are purely reactive
- Standard RL uses dangerous trial-and-error exploration
- My component implements **Safe Exploration** via Shadow Mode and Hybrid Arbitration
- Enables continuous learning WITHOUT risking production stability

---

## 2. Two Key Functions for PP1 Demonstration

### Function 1: State Vector Assembler  (Already Implemented)
- **Location:** `src/state_assembler.py`
- **Purpose:** Converts enriched context (metrics + dependency graph) into a 7-dimensional numerical state vector
- **Input:** `EnrichedContextPayload` (JSON from LiyanaArachchi's engine)
- **Output:** `np.ndarray` shape (7,) with normalized features

### Function 2: DQN Policy Inference Engine  (To be built Oct 9-10)
- **Location:** `src/dqn_policy_engine.py` (will create)
- **Purpose:** Evaluates state vector and outputs optimal recovery action
- **Input:** 7-dim state vector
- **Output:** Action (restart/scale_out/route/do_nothing) + Q-value (confidence)

---

## 3. Input/Output Flow

**[LiyanaArachchi's Engine]**
            ↓
**EnrichedContextPayload (JSON)**
            ↓
**[src/schema.py] - Validates & parses**
            ↓
**[src/state_assembler.py] - Converts to vector**
            ↓
**State Vector S_t [7-dim numpy array]**
            ↓
**[src/dqn_policy_engine.py] - DQN inference**
            ↓
**Action Decision {action: "restart", q_value: 0.85}**
            ↓
**[Hybrid Arbitration] → [Kubernetes API]**


---

## 4. Evidence of My Own Development

 Git commit history on `feat/adaptive-decision-engine/RL` branch
`src/schema.py` -   Pydantic models (Aug 18)
`src/state_assembler.py` - State vector transformation (Aug 18)
`tests/test_schema_and_state_assembler.py` - Comprehensive tests (Aug 18)
Development logs in `docs/development-log/`
Architecture diagrams in `docs/architecture/`

---

## 5. AI Assistance Disclosure

**AI Tools Used:**
- **Gemini/Claude:** Drafting academic text, generating test templates, formatting references
- **Verification Method:** 
  - Manually reviewed all AI-generated code for correctness
  - Validated mathematical formulations against MDP theory
  - Ran all unit tests to confirm expected behavior
  - Cross-referenced with proposal requirements

**My Contribution:**
- Designed the MDP state space formulation
- Created the schema data contract
- Implemented the state vector encoding logic
- Wrote all test cases
- Integrated with team components

---

## 6. 10-Day Sprint Plan (Oct 7-17)

| Day | Date | Focus | Deliverable |
|-----|------|-------|-------------|
| 1 | Oct 07 | Planning & Setup | GitHub Issues, dependencies, this document |
| 2 | Oct 08 | Polish Function 1 | Add Prometheus mock data, finalize tests |
| 3 | Oct 09 | Build Function 2 | Implement DQN Policy Engine |
| 4 | Oct 10 | Test Function 2 | Unit tests for DQN inference |
| 5 | Oct 11 | Integration | End-to-end demo: state → action |
| 6 | Oct 12 | Documentation | Update README, dev logs, AI disclosure |
| 7 | Oct 13 | Presentation Prep | Draft slides, record demo video |
| 8 | Oct 14 | Supervisor Feedback | Simulate review, refactor |
| 9 | Oct 15 | Test & Stabilize | Full test suite, code formatting |
| 10 | Oct 16 | Rehearse & PR | Final rehearsal, open PR to main |

---

## 7. Success Criteria for PP1

- [ ]  Function 1 demonstrates Input → Processing → Output
- [ ]  Function 2 demonstrates Input → Processing → Output
- [ ] Can explain the logic behind state vector encoding
- [ ] Can explain how DQN selects actions
- [ ] Tests pass and show expected outputs
- [ ] Git history shows regular commits (small, atomic)
- [ ] Development logs updated daily
- [ ] Can answer all 5 mandatory PP1 questions