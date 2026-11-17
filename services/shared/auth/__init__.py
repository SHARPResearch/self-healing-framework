"""Shared authentication package — users table, bcrypt hashing, JWT issue/verify.

Owned by the shared component, not by any single private component.
Private services (decision-engine, llm-copilot, ml-backend) only import
`get_current_user` from here; they never touch the users table.
"""