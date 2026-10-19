# Endpoint for Conversational RAG (User queries)

"""
Chat API Routes - Conversational Agent endpoint.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from loguru import logger
import uuid

from app.agents.conversational.rag_pipeline import rag_pipeline
from app.agents.evaluation.quality_scorer import quality_scorer
from app.agents.evaluation.metrics_exporter import metrics_exporter

router = APIRouter(prefix="/api/chat", tags=["Conversational Agent"])


class ChatRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    query_id: str
    response: str
    sources: list
    metrics: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any]


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    Process natural language query and return insights.
    
    Args:
        request: Chat request with query and optional context
    
    Returns:
        Chat response with answer, sources, and quality metrics
    """
    try:
        query_id = str(uuid.uuid4())
        
        # Process query through RAG pipeline
        result = await rag_pipeline.process_query(
            user_query=request.query,
            context=request.context
        )
        
        # Evaluate quality (if contexts available)
        metrics = {}
        if result.get("sources"):
            contexts = [source["text"] for source in result["sources"]]
            metrics = quality_scorer.evaluate_response(
                query=request.query,
                response=result["response"],
                contexts=contexts
            )
            
            # Export metrics
            metrics_exporter.export_metrics(
                query_id=query_id,
                metrics=metrics,
                metadata={"query": request.query}
            )
        
        return ChatResponse(
            query_id=query_id,
            response=result["response"],
            sources=result["sources"],
            metrics=metrics,
            metadata=result.get("metadata", {})
        )
        
    except Exception as e:
        logger.error(f" Chat query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics():
    """Get latest evaluation metrics."""
    try:
        latest = metrics_exporter.get_latest_metrics(n=10)
        averages = metrics_exporter.get_average_metrics()
        
        return {
            "latest": latest,
            "averages": averages
        }
    except Exception as e:
        logger.error(f" Metrics retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def ingest_telemetry(telemetry_data: Dict[str, Any]):
    """
    Ingest telemetry data into vector store.
    
    Args:
        telemetry_data: Raw telemetry data
    
    Returns:
        Number of chunks ingested
    """
    try:
        chunks_count = rag_pipeline.ingest_telemetry(telemetry_data)
        
        return {
            "status": "success",
            "chunks_ingested": chunks_count
        }
    except Exception as e:
        logger.error(f" Telemetry ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))