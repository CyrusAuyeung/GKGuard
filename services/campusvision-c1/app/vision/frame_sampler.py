from __future__ import annotations

from pathlib import Path
from typing import Iterator

import cv2
import numpy as np


def iter_video_frames(video_path: str | Path, every_seconds: float = 1.0) -> Iterator[tuple[float, np.ndarray]]:
    """Yield (timestamp_sec, frame_bgr)."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    if fps <= 0:
        fps = 25.0

    frame_step = max(1, int(round(fps * max(every_seconds, 0.1))))
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_idx % frame_step == 0:
            timestamp_sec = frame_idx / fps
            yield timestamp_sec, frame

        frame_idx += 1

    cap.release()
