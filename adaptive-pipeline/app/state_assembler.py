"""
state_assembler.py
The state assembler for Component 3.
Combines  features from the DB Reader and GCN Embedder into a single 55-dim state vector.
"""
import logging
import numpy as np
from .db_reader import fetch_anomaly_events, fetch_action_history
from .gcn_embedder import GCNEmbedder

log = logging.getLogger(__name__)

class StateAssembler:
    def __init__(self, topology_path: str = None):
        # Initialize the GCN Whisper Network
        self.gcn_embedder = GCNEmbedder(topology_path)
        
    def _get_anomaly_features(self, anomaly_id: str) -> np.ndarray:
        """Fetches and encodes the 6-dim anomaly features."""
        try:
            events = fetch_anomaly_events(limit=100)
            event = next((e for e in events if e['id'] == anomaly_id), None)
            if not event:
                return np.zeros(6)
                
            severity_map = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}
            severity_val = severity_map.get(str(event.get('severity', 'low')).lower(), 0.5)
            
            return np.array([
                float(event.get('anomaly_score', 0.0)),
                severity_val,
                float(event.get('deviation_sigma', 0.0)),
                float(event.get('confidence', 0.0)),
                1.0 if event.get('model_version') else 0.0,
                1.0 
            ])
            
        except Exception as e:
            log.error(f"Failed to fetch anomaly features: {e}")
            return np.zeros(6)

    def _get_gcn_embedding(self, service_id: str) -> np.ndarray:
        """Fetches the 32-dim graph embedding."""
        try:
            return self.gcn_embedder.get_embedding(service_id).numpy()
        except Exception as e:
            log.error(f"Failed to fetch GCN embedding: {e}")
            return np.zeros(32)

    def _get_history_and_telemetry(self, service_id: str) -> np.ndarray:
        """Fetches 5-dim action history and 12-dim telemetry placeholder."""
        try:
            # Fetch recent actions for this specific service
            actions = fetch_action_history(service_id=service_id, limit=5)
            
            # Encode the last 5 actions (1=RESTART, 2=SCALE, 3=ROUTE, 0=NONE)
            action_map = {"RESTART_SERVICE": 1, "SCALE_OUT": 2, "ROUTE_TRAFFIC": 3, "DO_NOTHING": 0}
            history = [action_map.get(a.get('action', 'DO_NOTHING'), 0) for a in actions[:5]]
            
            # Pad with zeros if less than 5 actions exist
            while len(history) < 5:
                history.append(0)
                
            # Placeholder for 12-dim telemetry (to be filled in Phase 4)
            telemetry = np.zeros(12)
            
            return np.concatenate([np.array(history), telemetry])
        except Exception as e:
            log.error(f"Failed to fetch history/telemetry: {e}")
            return np.zeros(17)

    def assemble(self, service_id: str, anomaly_id: str) -> np.ndarray:
        """
        The state assembler combines features from the anomaly, GCN embedding, and action history/telemetry into a single 55-dim state vector.
        Combines 6 (anomaly) + 32 (GCN) + 17 (telemetry/history) = 55 dimensions.
        """
        anomaly_feats = self._get_anomaly_features(anomaly_id)
        gcn_emb = self._get_gcn_embedding(service_id)
        history_telem = self._get_history_and_telemetry(service_id)
        
        state_vector = np.concatenate([anomaly_feats, gcn_emb, history_telem])
        
        # Normalize to [0, 1] range (Min-Max scaling)
        state_vector = np.clip(state_vector, 0, 1)
        
        return state_vector