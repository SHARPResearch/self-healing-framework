"""
feature_scaler.py
The 'Secret Sauce Bottle' for Component 3.
Mathematically shrinks any giant  down to the perfect [0, 1] size.
"""
import numpy as np

class MinMaxFeatureScaler:
    def __init__(self, feature_min: float = 0.0, feature_max: float = 1.0):
        self.feature_min = feature_min
        self.feature_max = feature_max

    def scale(self, vector: np.ndarray) -> np.ndarray:
        # Add a tiny epsilon (1e-8) to prevent division by zero
        scaled = (vector - self.feature_min) / (self.feature_max - self.feature_min + 1e-8)
        return np.clip(scaled, 0.0, 1.0)