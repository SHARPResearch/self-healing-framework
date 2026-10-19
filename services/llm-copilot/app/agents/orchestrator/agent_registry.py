# Registers all available agents

"""
Agent Registry - Manages available agents and their capabilities.
"""
from typing import Dict, List, Any
from loguru import logger


class AgentRegistry:
    """Registry for managing available agents."""

    def __init__(self):
        self.agents: Dict[str, Dict[str, Any]] = {}
        self._register_default_agents()

    def _register_default_agents(self):
        """Register default agents."""
        self.register_agent(
            name="conversational",
            description="RAG-based conversational agent for telemetry querying",
            capabilities=["chat", "query", "insights"],
            endpoint="/api/chat"
        )
        
        self.register_agent(
            name="reporting",
            description="Automated post-mortem report generation",
            capabilities=["postmortem", "report", "documentation"],
            endpoint="/api/postmortem"
        )
        
        self.register_agent(
            name="rca",
            description="Root Cause Analysis agent",
            capabilities=["rca", "diagnosis", "analysis"],
            endpoint="/api/rca"
        )
        
        self.register_agent(
            name="security",
            description="Security masking and PII scrubbing",
            capabilities=["mask", "scrub", "sanitize"],
            endpoint="/api/security"
        )
        
        logger.info(f" Registered {len(self.agents)} agents")

    def register_agent(
        self,
        name: str,
        description: str,
        capabilities: List[str],
        endpoint: str
    ) -> None:
        """Register a new agent."""
        self.agents[name] = {
            "name": name,
            "description": description,
            "capabilities": capabilities,
            "endpoint": endpoint,
            "status": "active"
        }

    def get_agent(self, name: str) -> Dict[str, Any]:
        """Get agent information by name."""
        return self.agents.get(name, {})

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all registered agents."""
        return list(self.agents.values())

    def get_agent_by_capability(self, capability: str) -> Dict[str, Any]:
        """Find agent by capability."""
        for agent in self.agents.values():
            if capability in agent["capabilities"]:
                return agent
        return {}


# Singleton instance
agent_registry = AgentRegistry()