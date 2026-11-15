# ChromaDB/FAISS

"""
Vector Store Manager - ChromaDB integration for RAG pipeline.
Stores telemetry embeddings for semantic retrieval.
"""
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Any
from loguru import logger
import os
import hashlib

from app.core.config import settings


class VectorStoreManager:
    """Manages ChromaDB vector store for telemetry data."""

    def __init__(self):
        self.client = None
        self.collection = None
        self.embedding_function = None
        self._initialize()

    def _initialize(self):
        """Initialize ChromaDB client and collection."""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(settings.vector_db_path), exist_ok=True)
            
            # FIX: Import and use SentenceTransformerEmbeddingFunction
            try:
                from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
                self.embedding_function = SentenceTransformerEmbeddingFunction(
                    model_name='all-MiniLM-L6-v2'
                )
                logger.info("Using SentenceTransformer embedding function")
            except Exception as e:
                logger.warning(f"Failed to load embedding function: {e}")
                self.embedding_function = None
            
            # Create persistent ChromaDB client
            self.client = chromadb.PersistentClient(
                path=settings.vector_db_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection for telemetry data
            self.collection = self.client.get_or_create_collection(
                name="telemetry_data",
                metadata={"hnsw:space": "cosine"},  # Use cosine similarity
                embedding_function=self.embedding_function
            )
            
            logger.info(f"ChromaDB initialized at {settings.vector_db_path}")
            logger.info(f"Collection '{self.collection.name}' has {self.collection.count()} documents")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def add_documents(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None
    ) -> None:
        """Add documents to vector store with optional pre-computed embeddings."""
        try:
            # FIX: Ensure metadata is flat (no nested dicts)
            clean_metadatas = []
            for metadata in metadatas:
                clean_metadata = {}
                for key, value in metadata.items():
                    # Only allow flat scalar values (str, int, float, bool)
                    if isinstance(value, (str, int, float, bool)):
                        clean_metadata[key] = value
                    elif isinstance(value, dict):
                        # Flatten nested dicts to strings
                        clean_metadata[key] = str(value)
                    else:
                        clean_metadata[key] = str(value)
                clean_metadatas.append(clean_metadata)
            
            self.collection.add(
                documents=documents,
                metadatas=clean_metadatas,
                ids=ids,
                embeddings=embeddings
            )
            logger.info(f"Added {len(documents)} documents to vector store")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query vector store for similar documents."""
        try:
            # FIX: Use query_texts parameter (plural)
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            logger.error(f"Failed to query vector store: {e}")
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        return {
            "name": self.collection.name,
            "count": self.collection.count(),
            "metadata": self.collection.metadata
        }


# Singleton instance
vector_store = VectorStoreManager()