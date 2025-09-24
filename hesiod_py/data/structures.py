"""Data structures used by the Hesiod runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = ["HeightMap", "Mesh"]


@dataclass
class HeightMap:
    data: np.ndarray
    bounds: tuple[float, float, float, float]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise ValueError("HeightMap expects a 2D numpy array")
        if not np.issubdtype(self.data.dtype, np.floating):
            self.data = self.data.astype(np.float32, copy=False)

    @property
    def resolution(self) -> tuple[int, int]:
        rows, cols = self.data.shape
        return int(rows), int(cols)

    def copy(self) -> HeightMap:
        return HeightMap(data=self.data.copy(), bounds=self.bounds, metadata=dict(self.metadata))


@dataclass
class Mesh:
    vertices: np.ndarray
    faces: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.vertices.ndim != 2 or self.vertices.shape[1] != 3:
            raise ValueError("Mesh.vertices must be shaped (n, 3)")
        if self.faces.ndim != 2 or self.faces.shape[1] not in (3, 4):
            raise ValueError("Mesh.faces must be shaped (n, 3) or (n, 4)")
        if not np.issubdtype(self.vertices.dtype, np.floating):
            self.vertices = self.vertices.astype(np.float32, copy=False)
        if not np.issubdtype(self.faces.dtype, np.integer):
            self.faces = self.faces.astype(np.int32, copy=False)

    @property
    def vertex_count(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def face_count(self) -> int:
        return int(self.faces.shape[0])

    def copy(self) -> Mesh:
        return Mesh(
            vertices=self.vertices.copy(),
            faces=self.faces.copy(),
            metadata=dict(self.metadata),
        )
