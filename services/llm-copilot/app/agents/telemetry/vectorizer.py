# Embeds telemetry for RAG (Retrieval-Augmented Generation)

"""
Telemetry Vectorizer - Converts telemetry context into embeddings for vector store.
"""
from typing import List, Dict, Any
from loguru import logger
import hashlib
from datetime import datetime


class TelemetryVectorizer:
    """Converts telemetry data into vector embeddings."""

    def __init__(self):
        self.embedding_model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize embedding model (using sentence-transformers)."""
        try:
            from sentence_transformers import SentenceTransformer
            # Use a lightweight, fast model
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model initialized (all-MiniLM-L6-v2)")
        except Exception as e:
            logger.warning(f"Failed to load embedding model: {e}")
            logger.info("Using fallback: simple hash-based embeddings")
            self.embedding_model = None

    def vectorize_context(self, context: Dict[str, Any]) -> List[float]:
        """Convert context to vector embedding."""
        try:
            # FIX: Extract text representation - handle both "text" and "context_text" keys
            context_text = context.get("text", context.get("context_text", ""))
            
            if self.embedding_model:
                # Use sentence-transformers
                embedding = self.embedding_model.encode(context_text).tolist()
                return embedding
            else:
                # Fallback: simple hash-based embedding (for testing)
                return self._fallback_embedding(context_text)
                
        except Exception as e:
            logger.error(f"Vectorization failed: {e}")
            return [0.0] * 384  # Return zero vector

    def _fallback_embedding(self, text: str) -> List[float]:
        """Fallback embedding using hash (for testing without model)."""
        # Generate a deterministic pseudo-embedding from text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert to float list (384 dimensions to match MiniLM)
        embedding = [(b / 255.0) for b in hash_bytes] * 12  # Repeat to get 384 dims
        return embedding[:384]

    def generate_document_id(self, context: Dict[str, Any]) -> str:
        """Generate unique document ID from context."""
        service = context.get("service", "unknown")
        timestamp = context.get("time_range", {}).get("end", datetime.now().isoformat())
        return f"{service}_{timestamp}"


# Singleton instance
vectorizer = TelemetryVectorizer()