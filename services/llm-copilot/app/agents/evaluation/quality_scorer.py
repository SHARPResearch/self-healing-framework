# Ragas/TruLens integration

"""
Quality Scorer - Evaluates RAG response quality using Ragas metrics.
"""
from typing import Dict, Any, List
from loguru import logger


class QualityScorer:
    """Evaluates quality of RAG responses."""

    def __init__(self):
        self.ragas_available = False
        self._initialize_ragas()

    def _initialize_ragas(self):
        """Initialize Ragas evaluation framework."""
        try:
            import ragas
            self.ragas_available = True
            logger.info(" Ragas evaluation framework available")
        except ImportError:
            logger.warning(" Ragas not installed - using fallback metrics")
            self.ragas_available = False

    def evaluate_response(
        self,
        query: str,
        response: str,
        contexts: List[str],
        ground_truth: str = None
    ) -> Dict[str, float]:
        """
        Evaluate RAG response quality.
        
        Args:
            query: User query
            response: Generated response
            contexts: Retrieved contexts
            ground_truth: Optional ground truth for comparison
        
        Returns:
            Dictionary of quality metrics
        """
        try:
            if self.ragas_available and ground_truth:
                return self._evaluate_with_ragas(query, response, contexts, ground_truth)
            else:
                return self._evaluate_fallback(query, response, contexts)
                
        except Exception as e:
            logger.error(f" Evaluation failed: {e}")
            return {"error": str(e)}

    def _evaluate_with_ragas(
        self,
        query: str,
        response: str,
        contexts: List[str],
        ground_truth: str
    ) -> Dict[str, float]:
        """Evaluate using Ragas framework."""
        try:
            from ragas import evaluate
            from ragas.metrics import faithfulness, answer_relevancy, context_precision
            from datasets import Dataset
            
            # Prepare data
            data = {
                "question": [query],
                "answer": [response],
                "contexts": [contexts],
                "ground_truth": [ground_truth]
            }
            
            dataset = Dataset.from_dict(data)
            
            # Evaluate
            results = evaluate(
                dataset=dataset,
                metrics=[faithfulness, answer_relevancy, context_precision]
            )
            
            return {
                "faithfulness": results["faithfulness"],
                "answer_relevancy": results["answer_relevancy"],
                "context_precision": results["context_precision"]
            }
            
        except Exception as e:
            logger.error(f" Ragas evaluation failed: {e}")
            return self._evaluate_fallback(query, response, contexts)

    def _evaluate_fallback(
        self,
        query: str,
        response: str,
        contexts: List[str]
    ) -> Dict[str, float]:
        """Fallback evaluation using simple heuristics."""
        metrics = {}
        
        # Context relevance (simple keyword overlap)
        query_words = set(query.lower().split())
        context_words = set(" ".join(contexts).lower().split())
        overlap = len(query_words & context_words) / max(len(query_words), 1)
        metrics["context_relevance"] = min(overlap * 2, 1.0)  # Scale up
        
        # Response length (penalize too short or too long)
        response_length = len(response.split())
        if 50 <= response_length <= 500:
            metrics["response_quality"] = 0.8
        elif response_length < 50:
            metrics["response_quality"] = 0.4
        else:
            metrics["response_quality"] = 0.6
        
        # Context utilization
        if contexts:
            metrics["context_utilization"] = 0.7
        else:
            metrics["context_utilization"] = 0.0
        
        return metrics


# Singleton instance
quality_scorer = QualityScorer()