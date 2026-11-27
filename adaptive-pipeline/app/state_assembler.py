"""
state_assembler.py
The Master  for Component 3.
Combines from the DB Reader and GCN Embedder into a single 55-dim state vector.
"""
import numpy as np
from .db_reader import fetch_anomaly_events
from .gcn_embedder import GCNEmbedder

class StateAssembler:
    def __init__(self, topology_path: str = None):
        # Initialize the GCN Whisper Network
        self.gcn_embedder = GCNEmbedder(topology_path)
        
    def _get_anomaly_features(self, anomaly_id: str) -> np.ndarray:
        """Fetches and encodes the 6-dim anomaly features."""
        events = fetch_anomaly_events(limit=100)
        # Find the specific event
        event = next((e for e in events if e['id'] == anomaly_id), None)
        if not event:
            return np.zeros(6)
            
        # Encode severity (simple mapping)
        severity_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
        severity_val = severity_map.get(str(event.get('severity', 'low')).lower(), 0.5)
        
        return np.array([
            float(event.get('anomaly_score', 0.0)),
            severity_val,
            float(event.get('deviation_sigma', 0.0)),
            float(event.get('confidence', 0.0)),
            1.0 if event.get('model_version') else 0.0,
            1.0 # placeholder for metric type encoding
        ])

    def _get_gcn_embedding(self, service_id: str) -> np.ndarray:
        """Fetches the 32-dim graph embedding."""
        return self.gcn_embedder.get_embedding(service_id).numpy()

    def _get_history_and_telemetry(self, service_id: str) -> np.ndarray:
        """Fetches 17-dim telemetry and history (simplified for now)."""
        # In a real scenario, this would fetch 12 telemetry dims and 5 history dims.
        # For now, we return a zero vector of size 17 to complete the 55-dim shape.
        # We will fill this in Phase 4 when we build the telemetry puller!
        return np.zeros(17)

    def assemble(self, service_id: str, anomaly_id: str) -> np.ndarray:
        """
        The Master Chef's main recipe.
        Combines 6 (anomaly) + 32 (GCN) + 17 (telemetry/history) = 55 dimensions.
        """
        anomaly_feats = self._get_anomaly_features(anomaly_id)
        gcn_emb = self._get_gcn_embedding(service_id)
        history_telem = self._get_history_and_telemetry(service_id)
        
        # Concatenate all ingredients
        state_vector = np.concatenate([anomaly_feats, gcn_emb, history_telem])
        
        # Normalize to [0, 1] range (Min-Max scaling)
        state_vector = np.clip(state_vector, 0, 1)
        
        return state_vector