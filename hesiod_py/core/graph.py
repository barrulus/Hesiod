"""Core graph data structures."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from typing import Any

__all__ = [
    "Connection",
    "Graph",
    "GraphError",
    "Node",
    "Port",
]


class GraphError(RuntimeError):
    """Raised when the graph model is in an invalid state."""


@dataclass(frozen=True, slots=True)
class Port:
    """Descriptor for node ports."""

    name: str
    data_type: str = "any"
    is_output: bool = False


@dataclass(slots=True)
class Connection:
    """Represents a directed connection between two node ports."""

    source_node: str
    source_port: str


@dataclass(slots=True)
class Node:
    """Graph node metadata and configuration."""

    key: str
    type: str
    title: str | None = None
    parameters: MutableMapping[str, Any] = field(default_factory=dict)
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def update_parameters(self, updates: Mapping[str, Any]) -> None:
        self.parameters.update(updates)


class Graph:
    """In-memory representation of a Hesiod node graph."""

    def __init__(self, *, name: str, metadata: Mapping[str, Any] | None = None) -> None:
        self.name = name
        self.metadata: dict[str, Any] = dict(metadata or {})
        self.nodes: dict[str, Node] = {}
        self._connections: dict[str, dict[str, Connection]] = defaultdict(dict)
        self._dependents: dict[str, set[str]] = defaultdict(set)
        self._dirty: set[str] = set()

    # Node Management -------------------------------------------------
    def add_node(self, node: Node) -> None:
        if node.key in self.nodes:
            raise GraphError(f"Node '{node.key}' already exists")
        self.nodes[node.key] = node
        self.mark_dirty(node.key)

    def remove_node(self, node_key: str) -> None:
        if node_key not in self.nodes:
            raise GraphError(f"Node '{node_key}' does not exist")
        for target in list(self._dependents.get(node_key, set())):
            for port_name, connection in list(self._connections[target].items()):
                if connection.source_node == node_key:
                    del self._connections[target][port_name]
                    self.mark_dirty(target)
            if not self._connections[target]:
                del self._connections[target]
            self._dependents[node_key].discard(target)
        self._dependents.pop(node_key, None)
        self.nodes.pop(node_key)
        self._connections.pop(node_key, None)
        self.mark_dirty(node_key)

    # Connections -----------------------------------------------------
    def connect(
        self,
        *,
        source_node: str,
        source_port: str,
        target_node: str,
        target_port: str,
    ) -> None:
        if source_node not in self.nodes:
            raise GraphError(f"Source node '{source_node}' does not exist")
        if target_node not in self.nodes:
            raise GraphError(f"Target node '{target_node}' does not exist")
        self._connections[target_node][target_port] = Connection(source_node, source_port)
        self._dependents[source_node].add(target_node)
        self.mark_dirty(target_node)

    def disconnect(self, *, node: str, port: str) -> None:
        if port in self._connections.get(node, {}):
            source = self._connections[node][port].source_node
            del self._connections[node][port]
            if not self._connections[node]:
                self._connections.pop(node, None)
            self._dependents[source].discard(node)
            self.mark_dirty(node)

    # Inspection ------------------------------------------------------
    def inputs_for(self, node_key: str) -> Mapping[str, Connection]:
        return self._connections.get(node_key, {})

    def dependencies_of(self, node_key: str) -> set[str]:
        return {conn.source_node for conn in self.inputs_for(node_key).values()}

    def dependents_of(self, node_key: str) -> set[str]:
        return set(self._dependents.get(node_key, set()))

    # Dirty tracking --------------------------------------------------
    def mark_dirty(self, node_key: str) -> None:
        if node_key in self.nodes:
            self._dirty.add(node_key)
            for dependent in self.dependents_of(node_key):
                self._dirty.add(dependent)

    def clear_dirty(self, node_key: str) -> None:
        self._dirty.discard(node_key)

    @property
    def dirty(self) -> set[str]:
        return set(self._dirty)

    # Ordering --------------------------------------------------------
    def topological_order(self, *, limit_to: Iterable[str] | None = None) -> Iterable[str]:
        if limit_to is None:
            target_nodes = set(self.nodes)
        else:
            target_nodes = {key for key in limit_to if key in self.nodes}
            if not target_nodes:
                return []

        sorter: TopologicalSorter[str] = TopologicalSorter()
        visited: set[str] = set()
        for node_key in target_nodes:
            self._add_dependencies_recursive(node_key, sorter, visited)

        try:
            order = tuple(sorter.static_order())
        except CycleError as exc:
            raise GraphError(f"Graph contains a cycle: {exc}") from exc
        return order

    def _add_dependencies_recursive(
        self,
        node_key: str,
        sorter: TopologicalSorter[str],
        visited: set[str],
    ) -> None:
        if node_key in visited:
            return
        visited.add(node_key)
        deps = self.dependencies_of(node_key)
        sorter.add(node_key, *deps)
        for dep in deps:
            self._add_dependencies_recursive(dep, sorter, visited)
