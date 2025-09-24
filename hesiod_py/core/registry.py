"""Registry for node implementations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .graph import Node

__all__ = [
    "ExecutionContext",
    "NodeHandler",
    "NodeMetadata",
    "NodeRegistry",
    "ParameterSpec",
    "PortSpec",
    "RegistryError",
]


class RegistryError(RuntimeError):
    """Raised when node handlers cannot be resolved."""


class ExecutionContext(Protocol):
    @property
    def state(self) -> MutableMapping[str, Any]: ...


class NodeHandler(Protocol):
    def __call__(
        self,
        node: Node,
        inputs: Mapping[str, Any],
        context: ExecutionContext,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class PortSpec:
    name: str
    data_type: str
    description: str = ""


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    param_type: str
    default: Any = None
    description: str = ""
    editor: str | None = None
    choices: Sequence[Any] | None = None


@dataclass(frozen=True)
class NodeMetadata:
    type: str
    label: str
    category: str
    inputs: tuple[PortSpec, ...] = ()
    outputs: tuple[PortSpec, ...] = ()
    parameters: tuple[ParameterSpec, ...] = ()
    description: str = ""
    tags: tuple[str, ...] = ()
    docs_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NodeDefinition:
    handler: NodeHandler
    description: str = ""
    metadata: NodeMetadata | None = None


class NodeRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, NodeDefinition] = {}

    def register(
        self,
        node_type: str,
        handler: NodeHandler,
        *,
        description: str = "",
        metadata: NodeMetadata | None = None,
    ) -> None:
        key = node_type.lower()
        if key in self._handlers:
            raise RegistryError(f"Handler already registered for '{node_type}'")
        self._handlers[key] = NodeDefinition(
            handler=handler,
            description=description,
            metadata=metadata,
        )

    def get(self, node_type: str) -> NodeDefinition:
        key = node_type.lower()
        if key not in self._handlers:
            raise RegistryError(f"No handler registered for '{node_type}'")
        return self._handlers[key]

    def describe(self, node_type: str) -> NodeMetadata:
        definition = self.get(node_type)
        if definition.metadata is None:
            raise RegistryError(f"Metadata not available for '{node_type}'")
        return definition.metadata

    def metadata(self) -> Iterable[NodeMetadata]:
        for definition in self._handlers.values():
            if definition.metadata is not None:
                yield definition.metadata

    def __contains__(self, node_type: str) -> bool:
        return node_type.lower() in self._handlers


registry = NodeRegistry()
