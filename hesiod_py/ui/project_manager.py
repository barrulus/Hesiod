
"""Project management utilities for the Hesiod UI."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Mapping, TYPE_CHECKING

from PySide6 import QtCore

from ..core.configuration import AppConfiguration, RuntimePaths
from ..core.project import Project, ProjectSerializer
from ..core.graph import Graph
from ..io.hsd import import_legacy_project, LegacyImportReport

if TYPE_CHECKING:
    from .controller import GraphController


class ProjectManager(QtCore.QObject):
    """Coordinate project lifecycle, persistence, and autosave."""

    project_changed = QtCore.Signal(str)
    dirty_changed = QtCore.Signal(bool)

    def __init__(
        self,
        controller: GraphController,
        *,
        autosave_dir: Path | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.project: Project | None = None
        self.current_path: Path | None = None
        self.dirty = False
        self._loading = False

        env_dir = os.environ.get("HESIOD_AUTOSAVE_DIR")
        base_autosave = autosave_dir or (Path(env_dir) if env_dir else Path.home() / ".hesiod" / "autosave")
        self.autosave_dir = Path(base_autosave)
        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        self.autosave_path = self.autosave_dir / "autosave.hproj"

        self.autosave_timer = QtCore.QTimer(self)
        self.autosave_timer.setInterval(60000)
        self.autosave_timer.timeout.connect(self.autosave)

    @contextmanager
    def _suspend_dirty(self) -> None:
        previous = self._loading
        self._loading = True
        try:
            yield
        finally:
            self._loading = previous

    def mark_dirty(self) -> None:
        if self._loading or self.project is None:
            return
        if not self.dirty:
            self.dirty = True
            self.dirty_changed.emit(True)
        if not self.autosave_timer.isActive():
            self.autosave_timer.start()

    def _set_clean(self) -> None:
        self.dirty = False
        self.dirty_changed.emit(False)

    def new_project(self, name: str = "Untitled") -> None:
        configuration = self._default_configuration(Path.cwd())
        graph = Graph(name=name)
        project = Project(name=name, graph=graph, configuration=configuration)
        with self._suspend_dirty():
            self.controller.clear(name=name)
            self.project = project
            self.current_path = None
            self._set_clean()
            self.project_changed.emit(project.name)
            self._update_autosave_path()
            self.autosave_timer.start()

    def load_project(self, path: Path) -> None:
        data = Path(path).read_text(encoding="utf-8")
        payload = json.loads(data)
        configuration = AppConfiguration.model_validate(payload.get("configuration", {}))
        project = ProjectSerializer.from_json(data, configuration=configuration)
        session = payload.get("metadata", {}).get("ui", {}).get("session")
        with self._suspend_dirty():
            self.controller.load_project(project, session)
            self.project = project
            self.current_path = Path(path)
            self._set_clean()
            self.project_changed.emit(project.name)
            self._update_autosave_path()
            self.autosave_timer.start()

    def save_project(self, path: Path | None = None, *, update_path: bool = True, clear_dirty: bool | None = None) -> Path:
        if self.project is None:
            self.new_project()
        assert self.project is not None
        target = Path(path or self.current_path or Path.cwd() / f"{self.project.name}.hproj")
        target.parent.mkdir(parents=True, exist_ok=True)
        graph_snapshot = self.controller.snapshot_graph()
        metadata = dict(self.project.metadata)
        metadata.setdefault("ui", {})["session"] = self.controller.node_graph.serialize_session()
        project = Project(
            name=self.project.name,
            graph=graph_snapshot,
            configuration=self.project.configuration,
            assets=dict(self.project.assets),
            metadata=metadata,
        )
        target.write_text(ProjectSerializer.to_json(project), encoding="utf-8")
        self.project = project
        if update_path:
            self.current_path = target
        if clear_dirty is None:
            clear_dirty = update_path
        if clear_dirty:
            with self._suspend_dirty():
                self._set_clean()
        if update_path:
            with self._suspend_dirty():
                self.project.name = target.stem
                self.controller.core_graph.name = self.project.name
                self.project_changed.emit(self.project.name)
                self._update_autosave_path()
        return target

    def save_project_as(self, path: Path) -> Path:
        saved_path = self.save_project(path, update_path=True, clear_dirty=True)
        return saved_path

    def autosave(self) -> None:
        if not self.project or not self.dirty:
            return
        self.autosave_dir.mkdir(parents=True, exist_ok=True)
        autosave_path = self.autosave_path
        try:
            self.save_project(autosave_path, update_path=False, clear_dirty=False)
        except Exception:
            return

    def import_legacy(self, path: Path) -> LegacyImportReport:
        configuration = self._default_configuration(path.parent)
        report = import_legacy_project(path, configuration)
        with self._suspend_dirty():
            self.controller.load_project(report.project, session=None)
            self.project = report.project
            self.current_path = None
            self.dirty = True
            self.dirty_changed.emit(True)
            self.project_changed.emit(report.project.name)
            self._update_autosave_path()
            self.autosave_timer.start()
        return report

    def _default_configuration(self, project_root: Path) -> AppConfiguration:
        cache_dir = project_root / ".hesiod" / "cache"
        asset_dir = project_root / "assets"
        return AppConfiguration(
            paths=RuntimePaths(
                project_root=project_root,
                cache_dir=cache_dir,
                asset_dir=asset_dir,
            )
        )

    def _update_autosave_path(self) -> None:
        if self.project is None:
            return
        slug = self.project.name.strip() or "autosave"
        sanitized = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in slug)
        self.autosave_path = self.autosave_dir / f"{sanitized.lower()}.hproj"
