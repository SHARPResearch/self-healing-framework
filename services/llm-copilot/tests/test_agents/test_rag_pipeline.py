"""
Tests for RAG Pipeline.
"""
import pytest
from app.agents.conversational.rag_pipeline import rag_pipeline
from app.agents.telemetry.context_builder import context_builder
from datetime import datetime


class TestRAGPipeline:
    """Test suite for RAG Pipeline."""

    @pytest.mark.asyncio
    async def test_process_query(self):
        """Test query processing."""
        query = "What is the CPU usage of payment service?"
        result = await rag_pipeline.process_query(query)
        
        assert "response" in result
        assert "sources" in result
        assert isinstance(result["response"], str)

    def test_ingest_telemetry(self):
        """Test telemetry ingestion."""
        telemetry_data = {
            "service": "test-service",
            "metrics": {
                "cpu_usage": {"value": 75, "avg": 60, "max": 85},
                "memory_usage": {"value": 70, "avg": 65, "max": 80},
                "error_rate": {"value": 2, "avg": 1.5}
            },
            "logs": [
                "INFO: Service started",
                "ERROR: Connection timeout",
                "WARNING: High memory usage"
            ],
            "time_range": {
                "start": datetime.now(),
                "end": datetime.now()
            }
        }
        
        chunks_count = rag_pipeline.ingest_telemetry(telemetry_data)
        assert chunks_count > 0


class TestContextBuilder:
    """Test suite for Context Builder."""

    def test_build_context(self):
        """Test context building."""
        metrics = {
            "cpu_usage": {"value": 80, "avg": 70, "max": 90},
            "memory_usage": {"value": 85, "avg": 75, "max": 95}
        }
        logs = ["ERROR: Service failed", "INFO: Restarting"]
        service_name = "test-service"
        time_range = {
            "start": datetime.now(),
            "end": datetime.now()
        }
        
        context = context_builder.build_context(
            metrics=metrics,
            logs=logs,
            service_name=service_name,
            time_range=time_range
        )
        
        assert "service" in context
        assert "metrics_summary" in context
        assert "anomaly_indicators" in context
        assert context["service"] == "test-service"