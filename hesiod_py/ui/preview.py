"""Preview widgets for visualising runtime outputs."""

from __future__ import annotations

from typing import Iterable

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ..data.structures import HeightMap

__all__ = ["PreviewWidget"]


class PreviewWidget(QtWidgets.QWidget):
    """Display heightmaps or image-like tensors in the UI."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hesiod-preview")
        self._pixmap: QtGui.QPixmap | None = None
        self._message = "No preview available."

        self.title_label = QtWidgets.QLabel("Preview", self)
        self.title_label.setObjectName("hesiod-preview-title")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)

        self.info_label = QtWidgets.QLabel("Select a node and run it to see output.", self)
        self.info_label.setObjectName("hesiod-preview-info")
        info_font = self.info_label.font()
        info_font.setPointSize(max(8, info_font.pointSize() - 2))
        self.info_label.setFont(info_font)
        self.info_label.setWordWrap(True)

        self.image_label = QtWidgets.QLabel(self._message, self)
        self.image_label.setObjectName("hesiod-preview-image")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(220, 220)
        self.image_label.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.image_label.installEventFilter(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        layout.addWidget(self.title_label)
        layout.addWidget(self.image_label, stretch=1)
        layout.addWidget(self.info_label)

    # ------------------------------------------------------------------
    def clear(self, message: str | None = None) -> None:
        self._pixmap = None
        if message is not None:
            self._message = message
        self.image_label.setPixmap(QtGui.QPixmap())
        self.image_label.setText(self._message)
        self.info_label.setText("Select a node and run it to see output.")

    def show_heightmap(self, heightmap: HeightMap, *, title: str) -> None:
        image, info = _heightmap_to_image(heightmap)
        self._set_preview(image, title, info)

    def show_array(self, array: np.ndarray, *, title: str, metadata: str | None = None) -> None:
        image, info = _array_to_image(array, metadata)
        self._set_preview(image, title, info)

    def show_message(self, title: str, message: str) -> None:
        self.title_label.setText(title)
        self.clear(message)

    # ------------------------------------------------------------------
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: D401
        if obj is self.image_label and event.type() == QtCore.QEvent.Resize:
            self._update_pixmap_display()
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    def _set_preview(self, image: QtGui.QImage, title: str, info: str) -> None:
        self.title_label.setText(title)
        self.info_label.setText(info)
        self._pixmap = QtGui.QPixmap.fromImage(image)
        self._update_pixmap_display()

    def _update_pixmap_display(self) -> None:
        if not self._pixmap or self._pixmap.isNull():
            self.image_label.setPixmap(QtGui.QPixmap())
            self.image_label.setText(self._message)
            return
        available = self.image_label.size()
        scaled = self._pixmap.scaled(
            available,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")


# ---------------------------------------------------------------------------

def _heightmap_to_image(heightmap: HeightMap) -> tuple[QtGui.QImage, str]:
    data = np.asarray(heightmap.data, dtype=np.float32)
    finite_mask = np.isfinite(data)
    if not finite_mask.any():
        normalised = np.zeros_like(data, dtype=np.uint8)
        vmin = vmax = 0.0
    else:
        vmin = float(data[finite_mask].min())
        vmax = float(data[finite_mask].max())
        if np.isclose(vmin, vmax):
            normalised = np.zeros_like(data, dtype=np.uint8)
        else:
            span = vmax - vmin
            normalised = ((data - vmin) / span).clip(0.0, 1.0)
            normalised = (normalised * 255.0).astype(np.uint8)
    image = _grayscale_image(normalised)
    rows, cols = heightmap.resolution
    info = f"HeightMap ? {cols}?{rows} ? range {vmin:.3f} ? {vmax:.3f}"
    return image, info


def _array_to_image(array: np.ndarray, metadata: str | None = None) -> tuple[QtGui.QImage, str]:
    data = np.asarray(array)
    info_parts: list[str] = []
    if metadata:
        info_parts.append(metadata)

    if data.ndim == 2:
        info_parts.append(f"Array ? {data.shape[1]}?{data.shape[0]}")
        image = _grayscale_image(_normalise_to_uint8(data))
    elif data.ndim == 3 and data.shape[2] in (3, 4):
        channels = data.shape[2]
        info_parts.append(f"Array ? {data.shape[1]}?{data.shape[0]}?{channels}")
        image = _color_image(_normalise_to_uint8(data), channels)
    else:
        raise TypeError("Preview arrays must be 2D or 3D with 3/4 channels")
    info = " ? ".join(info_parts) if info_parts else "Array"
    return image, info


def _normalise_to_uint8(data: np.ndarray) -> np.ndarray:
    if np.issubdtype(data.dtype, np.floating):
        finite = np.isfinite(data)
        if not finite.any():
            return np.zeros_like(data, dtype=np.uint8)
        clipped = np.clip(data, 0.0, 1.0)
        return (clipped * 255.0).astype(np.uint8)
    if np.issubdtype(data.dtype, np.integer):
        max_val = np.iinfo(data.dtype).max
        if max_val <= 0:
            return np.zeros_like(data, dtype=np.uint8)
        return (data.astype(np.float32) / float(max_val) * 255.0).clip(0.0, 255.0).astype(np.uint8)
    return np.asarray(data, dtype=np.uint8)


def _grayscale_image(array: np.ndarray) -> QtGui.QImage:
    if array.ndim != 2:
        raise ValueError("Grayscale images require a 2D array")
    array = np.ascontiguousarray(array)
    height, width = array.shape
    image = QtGui.QImage(array.data, width, height, array.strides[0], QtGui.QImage.Format_Grayscale8)
    return image.copy()


def _color_image(array: np.ndarray, channels: int) -> QtGui.QImage:
    array = np.ascontiguousarray(array)
    height, width, _ = array.shape
    if channels == 3:
        fmt = QtGui.QImage.Format_RGB888
    elif channels == 4:
        fmt = QtGui.QImage.Format_RGBA8888
    else:
        raise ValueError("Color images require 3 or 4 channels")
    image = QtGui.QImage(array.data, width, height, array.strides[0], fmt)
    return image.copy()
