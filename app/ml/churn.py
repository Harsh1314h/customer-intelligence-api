from dataclasses import dataclass

import numpy as np


@dataclass
class ChurnEnsemble:
    xgb_model: object
    neural_model: object
    feature_columns: list[str]
    xgb_weight: float = 0.65
    neural_weight: float = 0.35

    def predict_proba(self, frame):
        features = frame[self.feature_columns]
        xgb_probability = self.xgb_model.predict_proba(features)
        neural_probability = self.neural_model.predict_proba(features)
        probability = (self.xgb_weight * xgb_probability) + (self.neural_weight * neural_probability)
        return np.clip(probability, 0, 1)
