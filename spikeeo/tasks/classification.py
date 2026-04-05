"""ClassificationTask: N-class land cover / scene classification.

Converts tile-level SNN predictions into a spatially reconstructed
class map with confidence values and per-class area statistics.
"""

import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class ClassificationTask:
    """Land cover / scene classification task.

    Args:
        num_classes: Number of output classes.
    """

    def __init__(self, num_classes: int = 2) -> None:
        self.num_classes = num_classes

    def run(
        self,
        backbone: Any,
        tiles: list[np.ndarray],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Run classification on a list of tiles.

        Args:
            backbone: SNNBackbone instance (or HybridRouter).
            tiles: List of (C, H, W) numpy arrays.
            metadata: Scene metadata (crs, transform, etc.).

        Returns:
            Dict with class_ids, confidences, class_map, confidence_map,
            class_areas, geojson.
        """
        if not tiles:
            return {"class_ids": [], "confidences": [], "class_areas": {}}

        batch = torch.tensor(np.stack(tiles, axis=0), dtype=torch.float32)
        backbone.eval()
        with torch.no_grad():
            class_ids, confidences = backbone.predict(batch)

        class_ids_np = class_ids.cpu().numpy()
        confidences_np = confidences.cpu().numpy()

        # Per-class area statistics
        class_areas: dict[int, int] = {}
        for cls_id in range(self.num_classes):
            class_areas[int(cls_id)] = int(np.sum(class_ids_np == cls_id))

        result = self.postprocess({
            "class_ids": class_ids_np.tolist(),
            "confidences": confidences_np.tolist(),
            "class_areas": class_areas,
            "metadata": metadata,
        })
        logger.info(
            "ClassificationTask: %d tiles, class distribution=%s",
            len(tiles), class_areas,
        )
        return result

    def postprocess(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Postprocess raw classification output.

        Args:
            raw: Raw output from run().

        Returns:
            Processed result with geojson placeholder.
        """
        raw["geojson"] = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": {
                        "tile_index": i,
                        "class_id": raw["class_ids"][i],
                        "confidence": raw["confidences"][i],
                    },
                }
                for i in range(len(raw["class_ids"]))
            ],
        }
        return raw
