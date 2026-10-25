"""On-demand segmentation measurements for the two camera views."""

from pathlib import Path

import numpy as np


class SegmentationMeasurement:
    """Cache the segmentation models and measure their highest-confidence masks."""

    def __init__(self, camera1_model, camera2_model, conf_threshold=0.50):
        self.model_paths = (Path(camera1_model), Path(camera2_model))
        self.conf_threshold = conf_threshold
        self.models = None

    def load_models(self):
        if self.models is not None:
            return
        from ultralytics import YOLO

        models = []
        for path in self.model_paths:
            if not path.is_file():
                raise FileNotFoundError(f'Segmentation model not found: {path}')
            model = YOLO(str(path))
            if model.task != 'segment':
                raise ValueError(f'Model does not support segmentation: {path.name}')
            models.append(model)
        self.models = tuple(models)

    def _mask_size(self, model, frame):
        result = model(frame, conf=self.conf_threshold, verbose=False)[0]
        if result.masks is None or result.boxes is None:
            return None
        confidences = result.boxes.conf.cpu().numpy()
        for index in np.argsort(-confidences):
            # Mask polygons use coordinates in the original camera frame.
            points = np.asarray(result.masks.xy[int(index)])
            if points.ndim != 2 or len(points) < 3:
                continue
            width, height = np.ptp(points, axis=0)
            if np.isfinite((width, height)).all() and width > 0 and height > 0:
                return float(width), float(height)
        return None

    def measure(self, frame1, frame2, mm_per_pixel):
        """Return (length, width, height) in mm, or None if either mask is missing."""
        self.load_models()
        size1 = self._mask_size(self.models[0], frame1)
        size2 = self._mask_size(self.models[1], frame2)
        if size1 is None or size2 is None:
            return None
        return tuple(value * mm_per_pixel for value in (size1[0], *size2))
