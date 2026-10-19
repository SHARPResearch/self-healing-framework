# Converts raw metrics -> structured context

"""
Telemetry Context Builder - Converts raw telemetry into structured context for RAG.
"""
from typing import Dict, Any, List
from datetime import datetime
import json
from loguru import logger


class TelemetryContextBuilder:
    """Builds structured context from raw telemetry data."""

    def build_context(
        self,
        metrics: Dict[str, Any],
        logs: List[str],
        service_name: str,
        time_range: Dict[str, datetime]
    ) -> Dict[str, Any]:
        """
        Build structured context from telemetry data.
        
        Args:
            metrics: Prometheus metrics data
            logs: Application logs
            service_name: Name of the service
            time_range: Time range for the context
        
        Returns:
            Structured context dictionary
        """
        try:
            context = {
                "service": service_name,
                "time_range": {
                    "start": time_range["start"].isoformat(),
                    "end": time_range["end"].isoformat()
                },
                "metrics_summary": self._summarize_metrics(metrics),
                "log_highlights": self._extract_log_highlights(logs),
                "anomaly_indicators": self._detect_anomaly_indicators(metrics),
                "context_text": self._generate_context_text(metrics, logs, service_name)
            }
            
            logger.info(f" Built context for {service_name}")
            return context
            
        except Exception as e:
            logger.error(f" Failed to build context: {e}")
            return {"error": str(e)}

    def _summarize_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize key metrics."""
        summary = {}
        
        # Extract key metrics
        if "cpu_usage" in metrics:
            summary["cpu"] = {
                "current": metrics["cpu_usage"].get("value", 0),
                "avg": metrics["cpu_usage"].get("avg", 0),
                "max": metrics["cpu_usage"].get("max", 0)
            }
        
        if "memory_usage" in metrics:
            summary["memory"] = {
                "current": metrics["memory_usage"].get("value", 0),
                "avg": metrics["memory_usage"].get("avg", 0),
                "max": metrics["memory_usage"].get("max", 0)
            }
        
        if "error_rate" in metrics:
            summary["errors"] = {
                "current": metrics["error_rate"].get("value", 0),
                "avg": metrics["error_rate"].get("avg", 0)
            }
        
        if "latency" in metrics:
            summary["latency"] = {
                "p50": metrics["latency"].get("p50", 0),
                "p95": metrics["latency"].get("p95", 0),
                "p99": metrics["latency"].get("p99", 0)
            }
        
        return summary

    def _extract_log_highlights(self, logs: List[str]) -> List[str]:
        """Extract important log entries (errors, warnings)."""
        highlights = []
        keywords = ["error", "exception", "failed", "timeout", "warning", "critical"]
        
        for log in logs[:20]:  # Limit to first 20 logs
            if any(keyword in log.lower() for keyword in keywords):
                highlights.append(log.strip())
        
        return highlights[:10]  # Return top 10 highlights

    def _detect_anomaly_indicators(self, metrics: Dict[str, Any]) -> List[str]:
        """Detect potential anomaly indicators from metrics."""
        indicators = []
        
        # Check CPU
        if "cpu_usage" in metrics:
            cpu_val = metrics["cpu_usage"].get("value", 0)
            if cpu_val > 80:
                indicators.append(f"High CPU usage: {cpu_val}%")
        
        # Check Memory
        if "memory_usage" in metrics:
            mem_val = metrics["memory_usage"].get("value", 0)
            if mem_val > 85:
                indicators.append(f"High memory usage: {mem_val}%")
        
        # Check Error Rate
        if "error_rate" in metrics:
            err_val = metrics["error_rate"].get("value", 0)
            if err_val > 5:
                indicators.append(f"Elevated error rate: {err_val}%")
        
        # Check Latency
        if "latency" in metrics:
            p99_val = metrics["latency"].get("p99", 0)
            if p99_val > 1000:  # > 1 second
                indicators.append(f"High latency P99: {p99_val}ms")
        
        return indicators

    def _generate_context_text(
        self,
        metrics: Dict[str, Any],
        logs: List[str],
        service_name: str
    ) -> str:
        """Generate human-readable context text for RAG."""
        text_parts = [f"Service: {service_name}\n"]
        
        # Add metrics summary
        summary = self._summarize_metrics(metrics)
        if summary:
            text_parts.append("Metrics Summary:")
            for key, value in summary.items():
                text_parts.append(f"  - {key}: {json.dumps(value)}")
        
        # Add anomaly indicators
        indicators = self._detect_anomaly_indicators(metrics)
        if indicators:
            text_parts.append("\nAnomaly Indicators:")
            for indicator in indicators:
                text_parts.append(f"  {indicator}")
        
        # Add log highlights
        highlights = self._extract_log_highlights(logs)
        if highlights:
            text_parts.append("\nRecent Log Highlights:")
            for log in highlights[:5]:
                text_parts.append(f"  - {log[:200]}")  # Truncate long logs
        
        return "\n".join(text_parts)


# Singleton instance
context_builder = TelemetryContextBuilder()