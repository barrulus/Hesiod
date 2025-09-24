"""UI theming utilities for the Hesiod editor."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtGui, QtWidgets

from NodeGraphQt.constants import PipeLayoutEnum, ViewerEnum

__all__ = ["Theme", "DEFAULT_THEME", "apply_theme"]


@dataclass(frozen=True)
class Theme:
    name: str
    window_bg: str
    surface_bg: str
    surface_border: str
    preview_border: str
    text_primary: str
    text_muted: str
    accent: str
    selection: str
    graph_background: tuple[int, int, int]
    graph_grid: tuple[int, int, int]


DEFAULT_THEME = Theme(
    name="Midnight",
    window_bg="#1f232a",
    surface_bg="#272d36",
    surface_border="#313945",
    preview_border="#3a4350",
    text_primary="#f3f4f6",
    text_muted="#a3acbe",
    accent="#4f9dff",
    selection="#3a475a",
    graph_background=(31, 35, 42),
    graph_grid=(52, 58, 66),
)


def apply_theme(window: QtWidgets.QMainWindow, theme: Theme = DEFAULT_THEME) -> None:
    """Apply a consistent dark theme across the editor shell."""

    _apply_palette(theme)
    _apply_styles(window, theme)
    _apply_graph_theme(window, theme)


def _apply_palette(theme: Theme) -> None:
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    palette = app.palette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(theme.window_bg))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(theme.surface_bg))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(theme.surface_bg))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(theme.text_primary))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(theme.text_primary))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(theme.surface_bg))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(theme.text_primary))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(theme.selection))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(theme.text_primary))
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(theme.accent))
    app.setPalette(palette)


def _apply_styles(window: QtWidgets.QMainWindow, theme: Theme) -> None:
    style = f"""
    QMainWindow#hesiod-main {{
        background-color: {theme.window_bg};
        color: {theme.text_primary};
    }}
    QTabWidget::pane {{
        border: 1px solid {theme.surface_border};
        background: {theme.surface_bg};
    }}
    QTabBar::tab {{
        background: {theme.surface_bg};
        color: {theme.text_muted};
        padding: 6px 14px;
    }}
    QTabBar::tab:selected {{
        background: {theme.selection};
        color: {theme.text_primary};
    }}
    QSplitter::handle {{
        background-color: {theme.surface_border};
    }}
    #hesiod-node-tree {{
        background-color: {theme.surface_bg};
        color: {theme.text_primary};
        border: 1px solid {theme.surface_border};
    }}
    #hesiod-node-tree::item:selected {{
        background-color: {theme.selection};
        color: {theme.text_primary};
    }}
    #hesiod-properties {{
        background-color: {theme.surface_bg};
        color: {theme.text_primary};
        border: 1px solid {theme.surface_border};
    }}
    #hesiod-log-view {{
        background-color: {theme.surface_bg};
        color: {theme.text_primary};
        border: 1px solid {theme.surface_border};
    }}
    #hesiod-preview {{
        background-color: {theme.surface_bg};
        border: 1px solid {theme.preview_border};
        color: {theme.text_primary};
    }}
    #hesiod-preview QLabel#hesiod-preview-info {{
        color: {theme.text_muted};
    }}
    #hesiod-preview-image {{
        background-color: {theme.window_bg};
        border: 1px solid {theme.surface_border};
    }}
    QProgressBar#hesiod-progress {{
        background-color: {theme.surface_bg};
        border: 1px solid {theme.surface_border};
        border-radius: 2px;
    }}
    QProgressBar#hesiod-progress::chunk {{
        background-color: {theme.accent};
    }}
    """
    window.setStyleSheet(style)


def _apply_graph_theme(window: QtWidgets.QMainWindow, theme: Theme) -> None:
    graphs = []
    controller = getattr(window, 'controller', None)
    if controller is not None:
        graphs.append(controller.node_graph)
    documents = getattr(window, 'documents', None)
    if isinstance(documents, dict):
        graphs.extend(doc.controller.node_graph for doc in documents.values())
    seen: set[int] = set()
    for graph in graphs:
        if graph is None:
            continue
        ident = id(graph)
        if ident in seen:
            continue
        seen.add(ident)
        graph.set_background_color(*theme.graph_background)
        graph.set_grid_color(*theme.graph_grid)
        graph.set_grid_mode(ViewerEnum.GRID_DISPLAY_DOTS.value)
        graph.set_pipe_style(PipeLayoutEnum.CURVED.value)
        viewer = graph.viewer()
        if viewer is not None:
            viewer.viewport().update()
