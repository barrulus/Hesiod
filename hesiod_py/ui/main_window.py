"""PySide6 main window hosting the Hesiod node editor."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ..core.runtime import SchedulerError
from ..data.structures import HeightMap
from ._compat import ensure_distutils
from .controller import GraphController
from .preview import PreviewWidget
from .project_manager import ProjectManager
from .theme import DEFAULT_THEME, apply_theme

ensure_distutils()

from NodeGraphQt import NodesTreeWidget, PropertiesBinWidget  # noqa: E402  # type: ignore


@dataclass
class _Document:
    """Container for per-tab state."""

    controller: GraphController
    manager: ProjectManager
    palette: NodesTreeWidget
    properties: PropertiesBinWidget
    preview: PreviewWidget
    log_view: QtWidgets.QPlainTextEdit

    @property
    def graph_widget(self) -> QtWidgets.QWidget:
        return self.controller.node_graph.widget


class MainWindow(QtWidgets.QMainWindow):
    """Top-level window composing graph tabs, palette, and inspectors."""

    def __init__(
        self,
        controller: GraphController | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("hesiod-main")

        self.documents: dict[QtWidgets.QWidget, _Document] = {}
        self.controller: GraphController | None = None
        self._recent_dir: Path | None = None
        self._active_execution_doc: _Document | None = None

        self._setup_window()
        self._build_layout()
        self._create_actions()
        self._create_menus()
        self._wire_signals()

        self._create_document(
            initial_controller=controller,
            initialize=controller is None,
            activate=True,
        )
        self._apply_theme()

    # ------------------------------------------------------------------
    def _setup_window(self) -> None:
        self.setWindowTitle("Hesiod Python UI")
        self.resize(1280, 840)
        self.setStatusBar(QtWidgets.QStatusBar())
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setObjectName("hesiod-progress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        self.statusBar().addPermanentWidget(self.progress_bar)

    def _build_layout(self) -> None:
        self.palette_stack = QtWidgets.QStackedWidget()
        self.palette_stack.setObjectName("hesiod-palette-stack")

        self.graph_tabs = QtWidgets.QTabWidget()
        self.graph_tabs.setTabsClosable(True)
        self.graph_tabs.setMovable(True)
        self.graph_tabs.setDocumentMode(True)

        self.properties_stack = QtWidgets.QStackedWidget()
        self.preview_stack = QtWidgets.QStackedWidget()
        self.log_stack = QtWidgets.QStackedWidget()

        self.detail_tabs = QtWidgets.QTabWidget()
        self.detail_tabs.addTab(self.properties_stack, "Properties")
        self.detail_tabs.addTab(self.preview_stack, "Preview")
        self.detail_tabs.addTab(self.log_stack, "Logs")

        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_splitter.addWidget(self.palette_stack)

        right_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        right_splitter.addWidget(self.graph_tabs)
        right_splitter.addWidget(self.detail_tabs)
        right_splitter.setStretchFactor(0, 4)
        right_splitter.setStretchFactor(1, 1)

        main_splitter.addWidget(right_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        self.setCentralWidget(main_splitter)

    def _create_actions(self) -> None:
        toolbar = self.addToolBar("Execution")
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        self.run_selected_action = QtGui.QAction("Run Selection", self)
        self.run_selected_action.setShortcut(QtGui.QKeySequence("F5"))
        toolbar.addAction(self.run_selected_action)

        self.run_all_action = QtGui.QAction("Run All", self)
        self.run_all_action.setShortcut(QtGui.QKeySequence("Ctrl+F5"))
        toolbar.addAction(self.run_all_action)

    def _create_menus(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        self.new_action = QtGui.QAction("&New Project", self)
        self.new_action.setShortcut(QtGui.QKeySequence("Ctrl+N"))
        file_menu.addAction(self.new_action)

        self.open_action = QtGui.QAction("&Open Project...", self)
        self.open_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        file_menu.addAction(self.open_action)

        self.import_legacy_action = QtGui.QAction("Import &Legacy Project...", self)
        file_menu.addAction(self.import_legacy_action)

        file_menu.addSeparator()

        self.save_action = QtGui.QAction("&Save", self)
        self.save_action.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        file_menu.addAction(self.save_action)

        self.save_as_action = QtGui.QAction("Save &As...", self)
        self.save_as_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(self.save_as_action)

        file_menu.addSeparator()

        self.close_tab_action = QtGui.QAction("Close Tab", self)
        self.close_tab_action.setShortcut(QtGui.QKeySequence("Ctrl+W"))
        file_menu.addAction(self.close_tab_action)

        file_menu.addSeparator()

        self.exit_action = QtGui.QAction("E&xit", self)
        self.exit_action.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        file_menu.addAction(self.exit_action)

    def _wire_signals(self) -> None:
        self.run_selected_action.triggered.connect(self._run_selected)
        self.run_all_action.triggered.connect(self._run_all)
        self.new_action.triggered.connect(self._new_project)
        self.open_action.triggered.connect(self._open_project)
        self.import_legacy_action.triggered.connect(self._import_legacy_project)
        self.save_action.triggered.connect(self._save_current_project)
        self.save_as_action.triggered.connect(self._save_current_project_as)
        self.close_tab_action.triggered.connect(self._close_active_tab)
        self.exit_action.triggered.connect(self.close)
        self.graph_tabs.currentChanged.connect(self._on_active_tab_changed)
        self.graph_tabs.tabCloseRequested.connect(self._on_tab_close_requested)

    # ------------------------------------------------------------------
    def _create_document(
        self,
        *,
        name: str | None = None,
        initialize: bool = True,
        activate: bool = True,
        initial_controller: GraphController | None = None,
    ) -> _Document:
        controller = initial_controller or GraphController()
        controller.node_graph.widget.setObjectName("hesiod-node-graph")
        controller.node_graph.widget.setFocusPolicy(QtCore.Qt.StrongFocus)

        palette = NodesTreeWidget(node_graph=controller.node_graph)
        palette.setObjectName("hesiod-node-tree")
        palette.setMinimumWidth(260)

        properties = PropertiesBinWidget(node_graph=controller.node_graph)
        properties.setObjectName("hesiod-properties")

        preview = PreviewWidget()
        preview.setObjectName("hesiod-preview")

        log_view = QtWidgets.QPlainTextEdit()
        log_view.setObjectName("hesiod-log-view")
        log_view.setReadOnly(True)
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        log_view.setFont(font)

        manager = ProjectManager(controller)
        doc = _Document(
            controller=controller,
            manager=manager,
            palette=palette,
            properties=properties,
            preview=preview,
            log_view=log_view,
        )

        self.documents[doc.graph_widget] = doc
        self.palette_stack.addWidget(palette)
        self.properties_stack.addWidget(properties)
        self.preview_stack.addWidget(preview)
        self.log_stack.addWidget(log_view)
        tab_index = self.graph_tabs.addTab(doc.graph_widget, self._document_title(doc))
        self.graph_tabs.setTabToolTip(tab_index, "")

        self._bind_document_signals(doc)
        manager.project_changed.connect(partial(self._on_project_changed, doc))
        manager.dirty_changed.connect(partial(self._on_dirty_changed, doc))

        if initialize:
            project_name = name or self._untitled_name()
            manager.new_project(project_name)

        if activate:
            self.graph_tabs.setCurrentWidget(doc.graph_widget)
            self._show_document(doc)

        self._update_tab_metadata(doc)
        self._apply_theme()
        return doc

    def _bind_document_signals(self, doc: _Document) -> None:
        node_graph = doc.controller.node_graph

        def mark_dirty(*_: object) -> None:
            doc.manager.mark_dirty()

        for signal_name in ("node_created", "nodes_deleted", "node_moved", "property_changed", "port_connected", "port_disconnected"):
            signal = getattr(node_graph, signal_name, None)
            if signal is not None:
                signal.connect(mark_dirty)

    def _untitled_name(self) -> str:
        base = "Untitled"
        existing = {
            doc.manager.project.name
            for doc in self.documents.values()
            if doc.manager.project is not None
        }
        if base not in existing:
            return base
        index = 2
        while True:
            candidate = f"{base} {index}"
            if candidate not in existing:
                return candidate
            index += 1

    # ------------------------------------------------------------------
    def _current_document(self) -> _Document | None:
        widget = self.graph_tabs.currentWidget()
        if widget is None:
            return None
        return self.documents.get(widget)

    def _show_document(self, doc: _Document) -> None:
        self.controller = doc.controller
        self.palette_stack.setCurrentWidget(doc.palette)
        self.properties_stack.setCurrentWidget(doc.properties)
        self.preview_stack.setCurrentWidget(doc.preview)
        self.log_stack.setCurrentWidget(doc.log_view)
        self._update_window_title(doc)

    def _document_title(self, doc: _Document) -> str:
        project = doc.manager.project
        name = project.name if project is not None else "Untitled"
        return f"{name}{'*' if doc.manager.dirty else ''}"

    def _update_tab_metadata(self, doc: _Document) -> None:
        index = self.graph_tabs.indexOf(doc.graph_widget)
        if index == -1:
            return
        title = self._document_title(doc)
        self.graph_tabs.setTabText(index, title)
        tooltip = ""
        if doc.manager.current_path:
            tooltip = str(doc.manager.current_path)
        self.graph_tabs.setTabToolTip(index, tooltip)
        current = self._current_document()
        if current is doc:
            self._update_window_title(doc)

    def _update_window_title(self, doc: _Document) -> None:
        project = doc.manager.project
        name = project.name if project is not None else "Untitled"
        suffix = "*" if doc.manager.dirty else ""
        path = doc.manager.current_path
        if path:
            self.setWindowTitle(f"{name}{suffix} - Hesiod Python UI ({path})")
        else:
            self.setWindowTitle(f"{name}{suffix} - Hesiod Python UI")

    def _on_project_changed(self, doc: _Document, name: str) -> None:
        self._update_tab_metadata(doc)
        if doc is self._current_document():
            self.statusBar().showMessage(f"Project: {name}", 2000)

    def _on_dirty_changed(self, doc: _Document, dirty: bool) -> None:
        self._update_tab_metadata(doc)
        if doc is self._current_document():
            message = "Unsaved changes" if dirty else "All changes saved"
            self.statusBar().showMessage(message, 2000)

    # ------------------------------------------------------------------
    def _new_project(self) -> None:
        doc = self._create_document()
        self._log(doc, "Created new project tab.")

    def _open_project(self) -> None:
        start_dir = str(self._recent_dir or Path.cwd())
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Project",
            start_dir,
            "Hesiod Project (*.hproj)",
        )
        if not path_str:
            return
        path = Path(path_str)
        doc = self._create_document(initialize=False, activate=False)
        try:
            doc.manager.load_project(path)
        except Exception as exc:  # pragma: no cover - user interaction
            self._remove_document(doc, create_fallback=False)
            self._show_exception("Open Failed", f"Could not open project:\n{exc}")
            return
        self._recent_dir = path.parent
        self.graph_tabs.setCurrentWidget(doc.graph_widget)
        self._log(doc, f"Opened project '{path.name}'.")
        self._update_tab_metadata(doc)

    def _import_legacy_project(self) -> None:
        start_dir = str(self._recent_dir or Path.cwd())
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Import Legacy Project",
            start_dir,
            "Legacy Hesiod (*.hsd);;All Files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        doc = self._create_document(initialize=False, activate=False)
        try:
            report = doc.manager.import_legacy(path)
        except Exception as exc:  # pragma: no cover - user interaction
            self._remove_document(doc, create_fallback=False)
            self._show_exception("Import Failed", f"Could not import legacy project:\n{exc}")
            return
        self._recent_dir = path.parent
        self.graph_tabs.setCurrentWidget(doc.graph_widget)
        unsupported = getattr(report, "unsupported_nodes", [])
        if unsupported:
            unique = sorted(set(unsupported))
            self._log(
                doc,
                "Imported legacy project with unsupported nodes: " + ", ".join(unique),
            )
            self._show_information(
                "Legacy Import",
                f"Imported with {len(unique)} unsupported node type(s). See Logs tab for details.",
            )
        else:
            self._log(doc, f"Imported legacy project '{path.name}'.")
        self._update_tab_metadata(doc)

    def _save_current_project(self) -> None:
        doc = self._current_document()
        if doc is None:
            return
        saved = self._save_document(doc)
        if saved:
            self._log(doc, "Project saved.")

    def _save_current_project_as(self) -> None:
        doc = self._current_document()
        if doc is None:
            return
        saved = self._save_document(doc, force_dialog=True)
        if saved:
            self._log(doc, "Project saved to new location.")

    def _save_document(self, doc: _Document, *, force_dialog: bool = False) -> bool:
        manager = doc.manager
        path: Path | None = None
        if force_dialog or manager.current_path is None:
            start_dir = manager.current_path.parent if manager.current_path else (self._recent_dir or Path.cwd())
            path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save Project",
                str(start_dir),
                "Hesiod Project (*.hproj)",
            )
            if not path_str:
                return False
            path = Path(path_str)
        try:
            saved_path = manager.save_project(path)
        except Exception as exc:  # pragma: no cover - user interaction
            self._show_exception("Save Failed", f"Could not save project:\n{exc}")
            return False
        self._recent_dir = saved_path.parent
        self._update_tab_metadata(doc)
        return True

    def _close_active_tab(self) -> None:
        doc = self._current_document()
        if doc is None:
            return
        self._close_document(doc)

    def _on_active_tab_changed(self, index: int) -> None:
        doc = self._current_document()
        if doc is None:
            self.controller = None
            return
        self._show_document(doc)

    def _on_tab_close_requested(self, index: int) -> None:
        widget = self.graph_tabs.widget(index)
        if widget is None:
            return
        doc = self.documents.get(widget)
        if doc is not None:
            self._close_document(doc)

    def _close_document(self, doc: _Document) -> None:
        if not self._confirm_discard(doc):
            return
        self._remove_document(doc, create_fallback=True)

    def _remove_document(self, doc: _Document, *, create_fallback: bool) -> None:
        widget = doc.graph_widget
        index = self.graph_tabs.indexOf(widget)
        if index != -1:
            self.graph_tabs.removeTab(index)
        self.palette_stack.removeWidget(doc.palette)
        self.properties_stack.removeWidget(doc.properties)
        self.preview_stack.removeWidget(doc.preview)
        self.log_stack.removeWidget(doc.log_view)
        if widget in self.documents:
            del self.documents[widget]
        doc.manager.autosave_timer.stop()
        doc.manager.deleteLater()
        doc.palette.deleteLater()
        doc.properties.deleteLater()
        doc.preview.deleteLater()
        doc.log_view.deleteLater()
        widget.deleteLater()
        if not self.documents and create_fallback:
            self._create_document()
        self._apply_theme()

    def _confirm_discard(self, doc: _Document) -> bool:
        if not doc.manager.dirty:
            return True
        project = doc.manager.project
        name = project.name if project is not None else "Untitled"
        dialog = QtWidgets.QMessageBox(self)
        dialog.setIcon(QtWidgets.QMessageBox.Question)
        dialog.setWindowTitle("Unsaved Changes")
        dialog.setText(f"Save changes to '{name}' before closing?")
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel
        )
        dialog.setDefaultButton(QtWidgets.QMessageBox.Save)
        choice = dialog.exec()
        if choice == QtWidgets.QMessageBox.Cancel:
            return False
        if choice == QtWidgets.QMessageBox.Save:
            return self._save_document(doc)
        return True

    # ------------------------------------------------------------------
    def _set_execution_state(self, running: bool) -> None:
        self.run_selected_action.setEnabled(not running)
        self.run_all_action.setEnabled(not running)
        self.graph_tabs.setEnabled(not running)
        if running:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setValue(0)
            self.progress_bar.show()
        else:
            self.progress_bar.hide()
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)

    def _update_execution_progress(
        self,
        doc: _Document,
        scope: str,
        current: int,
        total: int,
        node_key: str,
    ) -> None:
        if doc is not self._active_execution_doc:
            return
        if total <= 0 or current == 0:
            self.statusBar().showMessage(f"Executing {scope}...")
            self.progress_bar.setRange(0, 0)
            return
        if self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(min(current, total))
        if node_key:
            name = doc.controller.node_display_name(node_key)
            self.statusBar().showMessage(f"Executing {scope}: {name} ({current}/{total})")

    def _execute_graph(
        self,
        scope: str,
        targets: Iterable[str] | None,
        *,
        doc: _Document | None = None,
    ) -> Mapping[str, Mapping[str, object]]:
        active_doc = doc or self._current_document()
        if active_doc is None:
            return {}
        self._active_execution_doc = active_doc
        self._set_execution_state(True)
        self.statusBar().showMessage(f"Executing {scope}...")

        def progress(current: int, total: int, node_key: str) -> None:
            self._update_execution_progress(active_doc, scope, current, total, node_key)

        try:
            results = active_doc.controller.evaluate(targets=targets, progress=progress)
        except SchedulerError as exc:
            self._report_error(active_doc, f"{scope.capitalize()} execution failed", exc)
            return {}
        except Exception as exc:  # pragma: no cover - defensive UI guard
            self._report_error(active_doc, "Unexpected failure during execution", exc)
            return {}
        finally:
            self._set_execution_state(False)
            self._active_execution_doc = None
        self._report_success(active_doc, scope, results)
        return results

    def _run_selected(self) -> None:
        doc = self._current_document()
        if doc is None:
            return
        targets = doc.controller.selected_node_ids()
        if targets:
            self._execute_graph("selection", targets, doc=doc)
        else:
            self._execute_graph("graph", None, doc=doc)

    def _run_all(self) -> None:
        doc = self._current_document()
        if doc is None:
            return
        self._execute_graph("graph", None, doc=doc)

    # ------------------------------------------------------------------
    def _log(self, doc: _Document, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        doc.log_view.appendPlainText(f"[{timestamp}] {message}")
        cursor = doc.log_view.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        doc.log_view.setTextCursor(cursor)

    def _report_success(self, doc: _Document, scope: str, results: Mapping[str, Mapping[str, object]]) -> None:
        if not results:
            self._log(doc, f"No nodes executed for {scope}.")
            self.statusBar().showMessage("No nodes executed", 4000)
            doc.preview.show_message("Preview", "No nodes executed.")
            return
        names = [doc.controller.node_display_name(node_id) for node_id in results.keys()]
        self._log(doc, f"Executed {len(results)} node(s): {', '.join(names)}")
        self.statusBar().showMessage(f"Executed {len(results)} node(s)", 4000)
        self._update_preview(doc, results)

    def _report_error(self, doc: _Document, context: str, error: Exception) -> None:
        message = str(error)
        self._log(doc, f"ERROR: {context}: {message}")
        QtWidgets.QMessageBox.critical(self, "Execution Error", f"{context}:\n{message}")
        self.statusBar().showMessage("Execution failed", 6000)
        doc.preview.show_message("Preview", "Execution failed. See logs for details.")

    def _update_preview(self, doc: _Document, results: Mapping[str, Mapping[str, object]]) -> None:
        items = list(results.items())
        for node_id, outputs in reversed(items):
            display_name = doc.controller.node_display_name(node_id)
            for port_name, value in outputs.items():
                title = f"{display_name} - {port_name}"
                if isinstance(value, HeightMap):
                    doc.preview.show_heightmap(value, title=title)
                    return
                if isinstance(value, np.ndarray):
                    doc.preview.show_array(value, title=title)
                    return
                if isinstance(value, Mapping):
                    for nested_key in ("heightmap", "texture"):
                        if nested_key not in value:
                            continue
                        nested_value = value[nested_key]
                        if isinstance(nested_value, HeightMap):
                            doc.preview.show_heightmap(nested_value, title=title)
                            return
                        if isinstance(nested_value, np.ndarray):
                            metadata = "Texture" if nested_key == "texture" else None
                            doc.preview.show_array(nested_value, title=title, metadata=metadata)
                            return
        doc.preview.show_message("Preview", "No previewable outputs in the latest run.")

    # ------------------------------------------------------------------
    @property
    def preview(self) -> PreviewWidget:
        doc = self._current_document()
        if doc is None:
            raise RuntimeError("No active document available")
        return doc.preview


    def _show_exception(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.critical(self, title, message)
        self.statusBar().showMessage(message, 6000)

    def _show_information(self, title: str, message: str) -> None:
        QtWidgets.QMessageBox.information(self, title, message)
        self.statusBar().showMessage(message, 4000)

    def _apply_theme(self) -> None:
        apply_theme(self, DEFAULT_THEME)

    # ------------------------------------------------------------------
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pragma: no cover - Qt integration
        for doc in list(self.documents.values()):
            if not doc.manager.dirty:
                continue
            if not self._confirm_discard(doc):
                event.ignore()
                return
        super().closeEvent(event)


__all__ = ["MainWindow"]
