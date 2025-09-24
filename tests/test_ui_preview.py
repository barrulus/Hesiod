"""Preview-related UI tests."""

from __future__ import annotations

import os

import numpy as np
import pytest
from PySide6 import QtWidgets

from hesiod_py.data.structures import HeightMap
from hesiod_py.ui.main_window import MainWindow
from hesiod_py.ui.preview import PreviewWidget
from hesiod_py.ui.theme import DEFAULT_THEME


def _ensure_qapplication() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_preview_widget_heightmap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    _ensure_qapplication()

    widget = PreviewWidget()
    data = np.linspace(0.0, 1.0, num=16, dtype=np.float32).reshape(4, 4)
    heightmap = HeightMap(data=data, bounds=(0, 1, 0, 1))

    widget.show_heightmap(heightmap, title="Test HeightMap")

    pixmap = widget.image_label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    assert "HeightMap" in widget.info_label.text()


def test_main_window_updates_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    _ensure_qapplication()

    window = MainWindow()
    assert window.controller.node_graph.background_color() == DEFAULT_THEME.graph_background
    assert DEFAULT_THEME.window_bg in window.styleSheet()
    controller = window.controller
    controller.create_node("noise.uniform", position=(0, 0))

    nodes_by_type = {
        getattr(node.__class__, "METADATA").type: node
        for node in controller.node_graph.all_nodes()
        if hasattr(node.__class__, "METADATA")
    }
    noise_node = nodes_by_type["noise.uniform"]

    window._execute_graph("selection", [str(noise_node.id)])

    pixmap = window.preview.image_label.pixmap()
    assert pixmap is not None and not pixmap.isNull()
    assert "HeightMap" in window.preview.info_label.text()
    assert not window.progress_bar.isVisible()
    window.close()
