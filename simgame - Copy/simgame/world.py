from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class RiverSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float

    def __post_init__(self) -> None:
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        length = (dx * dx + dy * dy) ** 0.5 or 1.0
        self.flow_x = dx / length
        self.flow_y = dy / length

    def contains_points(self, points) -> np.ndarray:
        p = np.asarray(points, dtype=np.float32)
        v = np.array([self.x2 - self.x1, self.y2 - self.y1], dtype=np.float32)
        w = p - np.array([self.x1, self.y1], dtype=np.float32)
        seg_len_sq = v.dot(v) + 1e-6
        t = np.clip((w @ v) / seg_len_sq, 0.0, 1.0)
        projection = np.array([self.x1, self.y1], dtype=np.float32) + np.outer(t, v)
        diff = p - projection
        dist_sq = np.sum(diff * diff, axis=1)
        return dist_sq < (self.width / 2) ** 2


def create_river(width: float, height: float) -> List[RiverSegment]:
    segments: List[RiverSegment] = []
    x = 50.0
    y = height / 2
    for _ in range(15):
        nx = x + random.uniform(70, 110)
        ny = y + random.uniform(-80, 80)
        ny = max(80.0, min(height - 80.0, ny))
        segments.append(RiverSegment(x, y, nx, ny, 45.0))
        x, y = nx, ny
        if x > width - 50:
            break
    return segments

