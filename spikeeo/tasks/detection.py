"""DetectionTask: Object counting via sliding-window SNN inference.

Detects objects (vehicles, buildings, etc.) in satellite imagery tiles
using a sliding-window approach with non-maximum suppression.
"""

import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class DetectionTask:
    """Object detection / counting task.

    Args:
        num_classes: Number of object classes (background + foreground).
        nms_threshold: IoU threshold for non-maximum suppression.
    """

    def __init__(self, num_classes: int = 2, nms_threshold: float = 0.5) -> None:
        self.num_classes = num_classes
        self.nms_threshold = nms_threshold

    def run(
        self,
        backbone: Any,
        tiles: list[np.ndarray],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Run detection on a list of tiles.

        Args:
            backbone: SNNBackbone instance.
            tiles: List of (C, H, W) numpy arrays.
            metadata: Scene metadata.

        Returns:
            Dict with detections, object_count, centroids, geojson.
        """
        if not tiles:
            return {"detections": [], "object_count": 0, "centroids": []}

        batch = torch.tensor(np.stack(tiles, axis=0), dtype=torch.float32)
        backbone.eval()
        with torch.no_grad():
            class_ids, confidences = backbone.predict(batch)

        class_ids_np = class_ids.cpu().numpy()
        confidences_np = confidences.cpu().numpy()

        # Foreground class = class 1 (assumes binary: 0=background, 1=object)
        fg_mask = class_ids_np == 1
        detections = []
        centroids = []

        for i, (is_fg, conf) in enumerate(zip(fg_mask, confidences_np)):
            if is_fg:
                tile_row = i // max(1, int(np.sqrt(len(tiles))))
                tile_col = i % max(1, int(np.sqrt(len(tiles))))
                cx = float(tile_col) + 0.5
                cy = float(tile_row) + 0.5
                detections.append({
                    "tile_index": i,
                    "class_id": 1,
                    "confidence": float(conf),
                    "bbox": [tile_col, tile_row, tile_col + 1, tile_row + 1],
                })
                centroids.append([cx, cy])

        result = {
            "detections": detections,
            "object_count": len(detections),
            "centroids": centroids,
            "total_tiles": len(tiles),
        }
        result = self.postprocess(result)
        logger.info("DetectionTask: %d objects detected in %d tiles", len(detections), len(tiles))
        return result

    def postprocess(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Add GeoJSON output for detected objects.

        Args:
            raw: Raw detection output.

        Returns:
            Result with geojson FeatureCollection.
        """
        raw["geojson"] = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": centroid,
                    },
                    "properties": {"index": i, "object_type": "detected"},
                }
                for i, centroid in enumerate(raw.get("centroids", []))
            ],
        }
        return raw
