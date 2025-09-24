"""Bridge between NodeGraphQt widgets and the Hesiod runtime."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional

from ..bootstrap import bootstrap as runtime_bootstrap
from ..core.graph import Graph, GraphError, Node
from ..core.project import Project, ProjectSerializer
from ..core.registry import NodeMetadata, NodeRegistry, ParameterSpec, registry as global_registry
from ..core.runtime import ExecutionCache, GraphScheduler, RuntimeContext
from ._compat import ensure_distutils
from .node_factory import HesiodNode, build_node_class

ensure_distutils()

from NodeGraphQt import NodeGraph  # noqa: E402  # type: ignore

LOGGER = logging.getLogger(__name__)


class GraphController:
    """Synchronises the interactive NodeGraph with the Hesiod runtime models."""
    def __init__(
        self,
        *,
        node_registry: NodeRegistry | None = None,
        configuration: Optional[Any] = None,
    ) -> None:
        self.registry = node_registry or global_registry
        self.configuration = configuration
        self.core_graph = Graph(name="Graph")
        self.node_graph = NodeGraph()
        self._cache = ExecutionCache()

        self._node_classes: dict[str, type[HesiodNode]] = {}
        self._node_identifiers: dict[str, str] = {}
        self._metadata_by_node_id: dict[str, NodeMetadata] = {}
        self._parameter_specs: dict[str, dict[str, ParameterSpec]] = {}
        self._parameter_properties: dict[str, dict[str, str]] = {}
        self._property_parameters: dict[str, dict[str, str]] = {}
        self._suspend_sync = False

        self._ensure_registry_seeded()
        self._register_nodes()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Public API
    def create_node(self, node_type: str, *, position: tuple[float, float] | None = None) -> None:
        identifier = self._node_identifiers.get(node_type)
        if identifier is None:
            raise KeyError(f"Unknown node type '{node_type}'")
        kwargs: dict[str, Any] = {"name": self._node_classes[node_type].NODE_NAME}
        if position:
            kwargs["pos"] = position
        self.node_graph.create_node(identifier, **kwargs)

    def selected_node_ids(self) -> list[str]:
        return [str(node.id) for node in self.node_graph.selected_nodes() if hasattr(node.__class__, "METADATA")]

    def evaluate(
        self,
        targets: Iterable[str] | None = None,
        *,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> Mapping[str, Mapping[str, object]]:
        scheduler = GraphScheduler(self.core_graph, cache=self._cache)
        context = RuntimeContext(graph=self.core_graph, configuration=self.configuration)
        return scheduler.evaluate(targets=targets, context=context, progress=progress)

    def evaluate_selected(
        self, *, progress: Callable[[int, int, str], None] | None = None
    ) -> Mapping[str, Mapping[str, object]]:
        targets = self.selected_node_ids()
        if not targets:
            return self.evaluate(progress=progress)
        return self.evaluate(targets, progress=progress)

    def node_display_name(self, node_id: str) -> str:
        qt_node = self.node_graph.get_node_by_id(node_id)
        if qt_node is None:
            return node_id
        return qt_node.name()

    # ------------------------------------------------------------------
    # Internal helpers
    def clear(self, *, name: str = "Graph") -> None:
        """Reset the runtime graph and clear the UI session."""

        self._suspend_sync = True
        self.node_graph.clear_session()
        try:
            self.node_graph.undo_stack().clear()
        except AttributeError:
            pass
        self.core_graph = Graph(name=name)
        self._cache = ExecutionCache()
        self._metadata_by_node_id.clear()
        self._suspend_sync = False


    def load_project(self, project: Project, session: Mapping[str, object] | None = None) -> None:
        """Load a project into the runtime and UI."""

        self.clear(name=project.graph.name)
        self.core_graph.metadata = dict(project.graph.metadata)
        self.core_graph.assets = dict(project.graph.assets)
        if session:
            self.node_graph.deserialize_session(session, clear_session=False, clear_undo_stack=True)
        else:
            self._populate_from_graph(project.graph)
        self._suspend_sync = True
        for node_key, saved_node in project.graph.nodes.items():
            runtime_node = self.core_graph.nodes.get(node_key)
            if runtime_node is None:
                continue
            runtime_node.parameters = dict(saved_node.parameters)
            runtime_node.metadata = dict(saved_node.metadata)
            qt_node = self.node_graph.get_node_by_id(node_key)
            if qt_node is None:
                continue
            node_class = self._node_classes.get(saved_node.type)
            if node_class is None:
                continue
            property_map = node_class.PARAMETER_PROPERTY_NAMES
            for param_name, value in saved_node.parameters.items():
                prop_name = property_map.get(param_name, param_name)
                if qt_node.get_property(prop_name) != value:
                    qt_node.set_property(prop_name, value)
        for node_key in list(self.core_graph.nodes.keys()):
            self.core_graph.clear_dirty(node_key)
        self._cache.clear()
        self._suspend_sync = False


    def snapshot_graph(self) -> Graph:
        """Return a deep copy of the current runtime graph."""

        graph_dict = ProjectSerializer._graph_to_dict(self.core_graph)
        return ProjectSerializer._graph_from_dict(graph_dict)


    def _populate_from_graph(self, graph: Graph) -> None:
        """Populate the UI and runtime from a stored graph when no session exists."""

        self._suspend_sync = True
        node_map: dict[str, HesiodNode] = {}
        for saved_node in graph.nodes.values():
            node_class = self._node_classes.get(saved_node.type)
            if node_class is None:
                LOGGER.warning("Unknown node type '%s' while loading project.", saved_node.type)
                continue
            metadata = self.registry.describe(saved_node.type)
            self._metadata_by_node_id[saved_node.key] = metadata
            identifier = f"{node_class.__identifier__}.{node_class.__name__}"
            qt_node = self.node_graph.create_node(identifier, name=saved_node.title or metadata.label)
            qt_node.model.id = saved_node.key
            qt_node.view.id = saved_node.key
            property_map = node_class.PARAMETER_PROPERTY_NAMES
            for param_name, value in saved_node.parameters.items():
                prop_name = property_map.get(param_name, param_name)
                qt_node.set_property(prop_name, value)
            runtime_node = Node(
                key=saved_node.key,
                type=saved_node.type,
                title=saved_node.title,
                parameters=dict(saved_node.parameters),
                metadata=dict(saved_node.metadata),
            )
            self.core_graph.add_node(runtime_node)
            node_map[saved_node.key] = qt_node
        for target_key in graph.nodes.keys():
            for port_name, connection in graph.inputs_for(target_key).items():
                source_key = connection.source_node
                source_port_name = connection.source_port
                source_qt = node_map.get(source_key)
                target_qt = node_map.get(target_key)
                if not source_qt or not target_qt:
                    continue
                source_port_names = list(source_qt.outputs().keys())
                target_port_names = list(target_qt.inputs().keys())
                try:
                    source_index = source_port_names.index(source_port_name)
                    target_index = target_port_names.index(port_name)
                except ValueError:
                    continue
                target_qt.set_input(target_index, source_qt.output(source_index))
                try:
                    self.core_graph.connect(
                        source_node=source_key,
                        source_port=source_port_name,
                        target_node=target_key,
                        target_port=port_name,
                    )
                except GraphError:
                    pass
        self._suspend_sync = False

    def _ensure_registry_seeded(self) -> None:
        try:
            next(iter(self.registry.metadata()))
        except StopIteration:
            runtime_bootstrap()
            try:
                next(iter(self.registry.metadata()))
            except StopIteration as exc:
                raise RuntimeError("Node registry is empty after bootstrap().") from exc

    def _register_nodes(self) -> None:
        metadatas = sorted(self.registry.metadata(), key=lambda item: (item.category, item.label))
        for metadata in metadatas:
            node_class = build_node_class(metadata)
            self.node_graph.register_node(node_class)
            identifier = f"{node_class.__identifier__}.{node_class.__name__}"
            self._node_classes[metadata.type] = node_class
            self._node_identifiers[metadata.type] = identifier
            self._parameter_specs[metadata.type] = {spec.name: spec for spec in metadata.parameters}
            self._parameter_properties[metadata.type] = dict(node_class.PARAMETER_PROPERTY_NAMES)
            self._property_parameters[metadata.type] = dict(node_class.PROPERTY_TO_PARAMETER)

    def _connect_signals(self) -> None:
        self.node_graph.node_created.connect(self._on_node_created)
        self.node_graph.nodes_deleted.connect(self._on_nodes_deleted)
        self.node_graph.port_connected.connect(self._on_port_connected)
        self.node_graph.port_disconnected.connect(self._on_port_disconnected)
        self.node_graph.property_changed.connect(self._on_property_changed)

    def _on_node_created(self, qt_node: HesiodNode) -> None:
        metadata = getattr(qt_node.__class__, "METADATA", None)
        if metadata is None:
            LOGGER.debug("Skipping unmanaged node %s", qt_node)
            return

        node_id = str(qt_node.id)
        parameters = self._collect_parameter_values(qt_node, metadata)
        runtime_node = Node(
            key=node_id,
            type=metadata.type,
            title=qt_node.name(),
            parameters=parameters,
        )
        try:
            self.core_graph.add_node(runtime_node)
        except GraphError as exc:
            LOGGER.error("Failed adding node %s: %s", node_id, exc)
            return
        self._metadata_by_node_id[node_id] = metadata

    def _on_nodes_deleted(self, node_ids: list[str]) -> None:
        for node_id in node_ids:
            key = str(node_id)
            if key in self.core_graph.nodes:
                try:
                    self.core_graph.remove_node(key)
                except GraphError as exc:
                    LOGGER.warning("Error removing node %s: %s", key, exc)
            self._metadata_by_node_id.pop(key, None)

    def _on_port_connected(self, input_port, output_port) -> None:
        if self._suspend_sync:
            return
        source_key = str(output_port.node().id)
        target_key = str(input_port.node().id)
        try:
            self.core_graph.connect(
                source_node=source_key,
                source_port=output_port.name(),
                target_node=target_key,
                target_port=input_port.name(),
            )
        except GraphError as exc:
            LOGGER.error("Connection failed (%s -> %s): %s", source_key, target_key, exc)

    def _on_port_disconnected(self, input_port, output_port) -> None:
        if self._suspend_sync:
            return
        target_key = str(input_port.node().id)
        self.core_graph.disconnect(node=target_key, port=input_port.name())

    def _on_property_changed(self, qt_node, name: str, value: object) -> None:
        if self._suspend_sync:
            return
        metadata = getattr(qt_node.__class__, "METADATA", None)
        if metadata is None:
            return
        node_id = str(qt_node.id)
        runtime_node = self.core_graph.nodes.get(node_id)
        if runtime_node is None:
            return
        if name == "name":
            runtime_node.title = str(value)
            return
        param_lookup = self._property_parameters.get(metadata.type, {})
        param_name = param_lookup.get(name)
        if param_name is None:
            return
        spec = self._parameter_specs.get(metadata.type, {}).get(param_name)
        if spec is None:
            return
        converted, should_delete = self._convert_parameter_value(spec, value)
        if should_delete:
            runtime_node.parameters.pop(param_name, None)
        else:
            runtime_node.parameters[param_name] = converted
        self.core_graph.mark_dirty(node_id)

    def _collect_parameter_values(self, qt_node, metadata: NodeMetadata) -> dict[str, object]:
        params: dict[str, object] = {}
        spec_map = self._parameter_specs.get(metadata.type, {})
        property_map = self._parameter_properties.get(metadata.type, {})
        for spec in metadata.parameters:
            prop_name = property_map.get(spec.name, spec.name)
            try:
                value = qt_node.get_property(prop_name)
            except Exception:  # pragma: no cover - NodeGraphQt raises on missing property
                LOGGER.debug("Property '%s' not available on node %s", prop_name, qt_node)
                continue
            converted, should_delete = self._convert_parameter_value(spec_map[spec.name], value)
            if should_delete:
                continue
            params[spec.name] = converted
        return params

    def _convert_parameter_value(self, spec: ParameterSpec, value: object) -> tuple[object | None, bool]:
        """Convert UI property values into runtime-friendly types.

        Returns a tuple of (value, delete_flag). When ``delete_flag`` is True the
        caller should remove the parameter from the runtime node entirely.
        """
        param_type = spec.param_type.lower()
        if param_type == "bool":
            return bool(value), False
        if param_type == "enum":
            return str(value), False
        if param_type == "path":
            string_value = str(value).strip() if value else ""
            if not string_value and spec.default is None:
                return None, True
            return string_value or str(spec.default or ""), False
        if param_type == "float":
            if value in ("", None):
                if spec.default is None:
                    return None, True
                return float(spec.default), False
            return float(value), False
        if param_type == "int":
            if value in ("", None):
                if spec.default is None:
                    return None, True
                return int(spec.default), False
            return int(value), False
        if value in ("", None) and spec.default is None:
            return None, True
        if value is None:
            return spec.default, False
        return value, False
