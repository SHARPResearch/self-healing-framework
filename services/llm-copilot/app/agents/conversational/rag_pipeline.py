# Conversational Agent

"""
Conversational RAG Pipeline - Translates natural language to telemetry queries.
"""
from typing import Dict, Any, List
from loguru import logger
import json

from app.agents.telemetry.context_builder import context_builder
from app.agents.telemetry.vectorizer import vectorizer
from app.agents.telemetry.chunker import chunker
from app.agents.security.masking import masking_agent
from app.db.vectorstore import vector_store
from app.services.llm_client import llm_client
from app.agents.conversational.prompts import RAG_SYSTEM_PROMPT, QUERY_TRANSLATION_PROMPT


class ConversationalRAGPipeline:
    """RAG pipeline for conversational telemetry querying."""

    async def process_query(self, user_query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process natural language query and return insights.
        
        Args:
            user_query: Natural language question from user
            context: Optional context (service name, time range, etc.)
        
        Returns:
            Dict with response, sources, and metadata
        """
        try:
            logger.info(f" Processing query: {user_query[:100]}...")
            
            # Step 1: Retrieve relevant telemetry from vector store
            retrieved_contexts = self._retrieve_context(user_query, n_results=3)
            
            # Step 2: Build augmented prompt
            augmented_prompt = self._build_augmented_prompt(user_query, retrieved_contexts)
            
            # Step 3: Mask sensitive data before sending to LLM
            masked_prompt = masking_agent.process(augmented_prompt)["sanitized_data"]
            
            # Step 4: Generate response using LLM
            response = llm_client.generate(
                prompt=masked_prompt,
                system_prompt=RAG_SYSTEM_PROMPT,
                temperature=0.3
            )
            
            # Step 5: Mask response before returning
            masked_response = masking_agent.process(response)["sanitized_data"]
            
            # Step 6: Prepare final result
            result = {
                "query": user_query,
                "response": masked_response,
                "sources": self._format_sources(retrieved_contexts),
                "metadata": {
                    "retrieved_chunks": len(retrieved_contexts),
                    "timestamp": context.get("timestamp") if context else None
                }
            }
            
            logger.info(f" Generated response with {len(retrieved_contexts)} sources")
            return result
            
        except Exception as e:
            logger.error(f" RAG pipeline failed: {e}")
            return {
                "query": user_query,
                "response": f"Sorry, I encountered an error: {str(e)}",
                "sources": [],
                "metadata": {"error": str(e)}
            }

    def _retrieve_context(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Retrieve relevant telemetry contexts from vector store."""
        try:
            # Query vector store
            results = vector_store.query(
                query_text=query,
                n_results=n_results
            )
            
            # Format results
            contexts = []
            if results and results.get("documents"):
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                    distance = results["distances"][0][i] if results.get("distances") else 0
                    
                    contexts.append({
                        "text": doc,
                        "metadata": metadata,
                        "relevance_score": 1 - distance  # Convert distance to similarity
                    })
            
            return contexts
            
        except Exception as e:
            logger.error(f" Context retrieval failed: {e}")
            return []

    def _build_augmented_prompt(self, query: str, contexts: List[Dict[str, Any]]) -> str:
        """Build augmented prompt with retrieved context."""
        context_text = "\n\n".join([
            f"[Source {i+1}] (Relevance: {ctx['relevance_score']:.2f})\n{ctx['text']}"
            for i, ctx in enumerate(contexts)
        ])
        
        prompt = QUERY_TRANSLATION_PROMPT.format(
            context=context_text if context_text else "No relevant telemetry data found.",
            query=query
        )
        
        return prompt

    def _format_sources(self, contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format retrieved contexts as sources."""
        sources = []
        for i, ctx in enumerate(contexts):
            sources.append({
                "id": i + 1,
                "text": ctx["text"][:200] + "..." if len(ctx["text"]) > 200 else ctx["text"],
                "metadata": ctx["metadata"],
                "relevance_score": ctx["relevance_score"]
            })
        return sources

    def ingest_telemetry(self, telemetry_data: Dict[str, Any]) -> int:
        """
        Ingest telemetry data into vector store.
        
        Args:
            telemetry_data: Raw telemetry data (metrics, logs, etc.)
        
        Returns:
            Number of chunks ingested
        """
        try:
            # Step 1: Build context
            context = context_builder.build_context(
                metrics=telemetry_data.get("metrics", {}),
                logs=telemetry_data.get("logs", []),
                service_name=telemetry_data.get("service", "unknown"),
                time_range=telemetry_data.get("time_range", {})
            )
            
            # Step 2: Chunk context
            chunks = chunker.chunk_context(context)
            
            # Step 3: Vectorize and store
            documents = []
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                # Vectorize
                embedding = vectorizer.vectorize_context(chunk)
                
                # Prepare for storage
                documents.append(chunk["text"])
                metadatas.append(chunk["metadata"])
                ids.append(vectorizer.generate_document_id({
                    **chunk["metadata"],
                    "chunk_index": i
                }))
            
            # Add to vector store
            if documents:
                vector_store.add_documents(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=None  # Let ChromaDB compute embeddings
                )
            
            logger.info(f" Ingested {len(chunks)} chunks from telemetry data")
            return len(chunks)
            
        except Exception as e:
            logger.error(f" Telemetry ingestion failed: {e}")
            return 0


# Singleton instance
rag_pipeline = ConversationalRAGPipeline()