"""AnomalyTask: Anomaly detection for fire, spill, and deforestation events.

Compares current tiles against a baseline distribution to produce
anomaly scores highlighting unusual spectral signatures.
"""

import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class AnomalyTask:
    """Anomaly detection task.

    Detects unusual spectral patterns by comparing SNN confidence
    distributions against expected baselines.

    Args:
        anomaly_threshold: Minimum anomaly score to flag a tile.
    """

    def __init__(self, anomaly_threshold: float = 0.6) -> None:
        self.anomaly_threshold = anomaly_threshold

    def run(
        self,
        backbone: Any,
        tiles: list[np.ndarray],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Run anomaly detection on a list of tiles.

        Args:
            backbone: SNNBackbone instance.
            tiles: List of (C, H, W) tiles.
            metadata: Scene metadata. May include 'baseline_stats'
                (mean/std of expected confidences).

        Returns:
            Dict with anomaly_scores, anomaly_mask, anomaly_count, geojson.
        """
        if not tiles:
            return {"anomaly_scores": [], "anomaly_count": 0}

        batch = torch.tensor(np.stack(tiles, axis=0), dtype=torch.float32)
        backbone.eval()
        with torch.no_grad():
            class_ids, confidences = backbone.predict(batch)

        confidences_np = confidences.cpu().numpy()

        # Anomaly score = inverted confidence (low confidence = unusual)
        anomaly_scores = 1.0 - confidences_np
        anomaly_mask = anomaly_scores > self.anomaly_threshold

        baseline = metadata.get("baseline_stats", {})
        baseline_mean = baseline.get("mean_confidence", 0.85)
        # Normalise relative to baseline
        anomaly_scores_norm = np.clip(anomaly_scores / (1.0 - baseline_mean + 1e-6), 0.0, 1.0)

        result = {
            "anomaly_scores": anomaly_scores_norm.tolist(),
            "anomaly_mask": anomaly_mask.tolist(),
            "anomaly_count": int(anomaly_mask.sum()),
            "anomaly_pct": float(anomaly_mask.mean() * 100),
        }
        result = self.postprocess(result)
        logger.info(
            "AnomalyTask: %d anomalies detected in %d tiles (%.1f%%)",
            result["anomaly_count"], len(tiles), result["anomaly_pct"],
        )
        return result

    def postprocess(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Add GeoJSON representation of anomalous areas.

        Args:
            raw: Raw anomaly detection output.

        Returns:
            Result with geojson.
        """
        anomaly_mask = raw.get("anomaly_mask", [])
        anomaly_scores = raw.get("anomaly_scores", [])
        features = [
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "tile_index": i,
                    "anomaly_score": anomaly_scores[i] if i < len(anomaly_scores) else 0.0,
                },
            }
            for i, is_anomaly in enumerate(anomaly_mask)
            if is_anomaly
        ]
        raw["geojson"] = {"type": "FeatureCollection", "features": features}
        return raw
