# NL -> PromQL/SQL

"""
Query Translator - Converts natural language to structured queries.
"""
from typing import Dict, Any
from loguru import logger
import re


class QueryTranslator:
    """Translates natural language queries to structured telemetry queries."""

    def translate(self, query: str) -> Dict[str, Any]:
        """
        Translate natural language to structured query.
        
        Args:
            query: Natural language question
        
        Returns:
            Structured query dictionary
        """
        try:
            # Extract key components
            service = self._extract_service(query)
            metric_type = self._extract_metric_type(query)
            time_range = self._extract_time_range(query)
            
            structured_query = {
                "original": query,
                "service": service,
                "metric_type": metric_type,
                "time_range": time_range,
                "query_type": self._classify_query(query)
            }
            
            logger.info(f" Translated query: {structured_query}")
            return structured_query
            
        except Exception as e:
            logger.error(f" Query translation failed: {e}")
            return {"original": query, "error": str(e)}

    def _extract_service(self, query: str) -> str:
        """Extract service name from query."""
        # Simple pattern matching (can be enhanced with NER)
        service_patterns = [
            r'(?:service|svc)\s+(\w+)',
            r'(\w+[-_]?service)',
            r'(\w+[-_]?svc)'
        ]
        
        for pattern in service_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return "unknown"

    def _extract_metric_type(self, query: str) -> str:
        """Extract metric type from query."""
        metric_keywords = {
            "cpu": ["cpu", "processor", "compute"],
            "memory": ["memory", "ram", "heap"],
            "latency": ["latency", "response time", "delay"],
            "error_rate": ["error", "exception", "failure"],
            "throughput": ["throughput", "requests", "traffic"]
        }
        
        query_lower = query.lower()
        for metric_type, keywords in metric_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return metric_type
        
        return "general"

    def _extract_time_range(self, query: str) -> Dict[str, str]:
        """Extract time range from query."""
        time_patterns = {
            "last_5min": r"(?:last|past)\s+5\s*(?:min|minutes)",
            "last_15min": r"(?:last|past)\s+15\s*(?:min|minutes)",
            "last_1hour": r"(?:last|past)\s+(?:1|one)\s*(?:hour|hr)",
            "last_24hours": r"(?:last|past)\s+(?:24|twenty[- ]?four)\s*(?:hours|hrs)",
            "today": r"today",
            "yesterday": r"yesterday"
        }
        
        query_lower = query.lower()
        for time_range, pattern in time_patterns.items():
            if re.search(pattern, query_lower):
                return {"type": time_range}
        
        return {"type": "default"}

    def _classify_query(self, query: str) -> str:
        """Classify query type."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["why", "cause", "root"]):
            return "diagnosis"
        elif any(word in query_lower for word in ["how", "performance", "health"]):
            return "status"
        elif any(word in query_lower for word in ["trend", "change", "compare"]):
            return "comparison"
        else:
            return "general"


# Singleton instance
query_translator = QueryTranslator()