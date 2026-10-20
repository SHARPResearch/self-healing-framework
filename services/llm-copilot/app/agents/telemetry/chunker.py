# Splits logs into chunks

"""
Telemetry Chunker - Splits telemetry data into manageable chunks for vectorization.
"""
from typing import List, Dict, Any
from loguru import logger


class TelemetryChunker:
    """Splits telemetry data into chunks for vector store ingestion."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_context(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split context into chunks.
        
        Args:
            context: Telemetry context dictionary
        
        Returns:
            List of chunk dictionaries
        """
        try:
            chunks = []
            context_text = context.get("context_text", "")
            
            # Split text into chunks
            text_chunks = self._split_text(context_text)
            
            for i, chunk_text in enumerate(text_chunks):
                chunk = {
                    "text": chunk_text,
                    "metadata": {
                        "service": context.get("service"),
                        "chunk_index": i,
                        "total_chunks": len(text_chunks),
                        "time_range": context.get("time_range")
                    }
                }
                chunks.append(chunk)
            
            logger.info(f" Split context into {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f" Chunking failed: {e}")
            return []

    def _split_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap."""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap  # Overlap
        
        return chunks


# Singleton instance
chunker = TelemetryChunker()