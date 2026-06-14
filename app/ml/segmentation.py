from dataclasses import dataclass

import numpy as np


@dataclass
class SegmentPrediction:
    cluster_id: int
    segment: str
    distance_to_centroid: float


@dataclass
class CustomerSegmenter:
    pipeline: object
    feature_columns: list[str]
    cluster_labels: dict[int, str]

    def predict_customer(self, frame) -> SegmentPrediction:
        features = frame[self.feature_columns]
        cluster_id = int(self.pipeline.predict(features)[0])
        scaler = self.pipeline.named_steps["scaler"]
        kmeans = self.pipeline.named_steps["kmeans"]
        scaled_features = scaler.transform(features)
        distance = float(np.linalg.norm(scaled_features[0] - kmeans.cluster_centers_[cluster_id]))
        return SegmentPrediction(
            cluster_id=cluster_id,
            segment=self.cluster_labels.get(cluster_id, f"segment-{cluster_id}"),
            distance_to_centroid=distance,
        )
