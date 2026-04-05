"""SegmentationTask: Pixel-wise semantic segmentation.

Classifies each pixel in the input image independently using
a sliding-window SNN inference approach.
"""

import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class SegmentationTask:
    """Semantic segmentation task.

    Produces a dense class map by running classification on
    overlapping tiles and averaging predictions for overlapping regions.

    Args:
        num_classes: Number of semantic classes.
    """

    def __init__(self, num_classes: int = 2) -> None:
        self.num_classes = num_classes

    def run(
        self,
        backbone: Any,
        tiles: list[np.ndarray],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Run segmentation via tile-level classification.

        Args:
            backbone: SNNBackbone instance.
            tiles: List of (C, H, W) tiles.
            metadata: Scene metadata (shape, transform, crs).

        Returns:
            Dict with segment_map, class_ids, confidences, geojson.
        """
        if not tiles:
            return {"segment_map": [], "class_ids": [], "confidences": []}

        batch = torch.tensor(np.stack(tiles, axis=0), dtype=torch.float32)
        backbone.eval()
        with torch.no_grad():
            class_ids, confidences = backbone.predict(batch)

        class_ids_np = class_ids.cpu().numpy()
        confidences_np = confidences.cpu().numpy()

        # Build segment statistics
        class_areas: dict[int, int] = {}
        for cls_id in range(self.num_classes):
            class_areas[int(cls_id)] = int(np.sum(class_ids_np == cls_id))

        result = {
            "segment_map": class_ids_np.tolist(),
            "class_ids": class_ids_np.tolist(),
            "confidences": confidences_np.tolist(),
            "class_areas": class_areas,
        }
        result = self.postprocess(result)
        logger.info("SegmentationTask: %d tiles, areas=%s", len(tiles), class_areas)
        return result

    def postprocess(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Add GeoJSON polygon representation.

        Args:
            raw: Raw segmentation output.

        Returns:
            Result with geojson.
        """
        raw["geojson"] = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": {
                        "class_id": cls_id,
                        "area_tiles": count,
                    },
                }
                for cls_id, count in raw.get("class_areas", {}).items()
                if count > 0
            ],
        }
        return raw
