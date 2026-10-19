# Publishes scores to dashboard

"""
Metrics Exporter - Exports evaluation metrics to dashboard.
"""
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger
import json
import os


class MetricsExporter:
    """Exports evaluation metrics for dashboard consumption."""

    def __init__(self, metrics_file: str = "data/metrics.json"):
        self.metrics_file = metrics_file
        self.metrics_history: List[Dict[str, Any]] = []
        self._load_history()

    def _load_history(self):
        """Load metrics history from file."""
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r') as f:
                    self.metrics_history = json.load(f)
                logger.info(f" Loaded {len(self.metrics_history)} metrics records")
        except Exception as e:
            logger.warning(f" Failed to load metrics history: {e}")
            self.metrics_history = []

    def export_metrics(
        self,
        query_id: str,
        metrics: Dict[str, float],
        metadata: Dict[str, Any] = None
    ) -> None:
        """
        Export metrics to storage.
        
        Args:
            query_id: Unique query identifier
            metrics: Evaluation metrics
            metadata: Additional metadata
        """
        try:
            record = {
                "query_id": query_id,
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "metadata": metadata or {}
            }
            
            self.metrics_history.append(record)
            self._save_history()
            
            logger.info(f" Exported metrics for query {query_id}")
            
        except Exception as e:
            logger.error(f" Metrics export failed: {e}")

    def _save_history(self):
        """Save metrics history to file."""
        try:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics_history, f, indent=2)
        except Exception as e:
            logger.error(f" Failed to save metrics: {e}")

    def get_latest_metrics(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get latest n metrics records."""
        return self.metrics_history[-n:]

    def get_average_metrics(self) -> Dict[str, float]:
        """Calculate average metrics across all records."""
        if not self.metrics_history:
            return {}
        
        all_metrics = [record["metrics"] for record in self.metrics_history]
        avg_metrics = {}
        
        for key in all_metrics[0].keys():
            values = [m.get(key, 0) for m in all_metrics if key in m]
            if values:
                avg_metrics[key] = sum(values) / len(values)
        
        return avg_metrics


# Singleton instance
metrics_exporter = MetricsExporter()