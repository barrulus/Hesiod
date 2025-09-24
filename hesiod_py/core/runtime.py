"""Graph execution scheduler."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, MutableMapping
from dataclasses import dataclass, field

import numpy as np

from .configuration import AppConfiguration
from .graph import Graph, Node
from .registry import NodeRegistry, registry

__all__ = ["ExecutionCache", "RuntimeContext", "GraphScheduler", "SchedulerError"]


class SchedulerError(RuntimeError):
    """Raised when the scheduler fails to execute a graph."""


@dataclass
class ExecutionCache:
    _values: MutableMapping[str, Mapping[str, object]] = field(default_factory=dict)
    _signatures: MutableMapping[str, str] = field(default_factory=dict)

    def get(self, node_key: str) -> Mapping[str, object] | None:
        return self._values.get(node_key)

    def store(self, node_key: str, signature: str, outputs: Mapping[str, object]) -> None:
        self._values[node_key] = outputs
        self._signatures[node_key] = signature

    def is_valid(self, node_key: str, signature: str) -> bool:
        return self._signatures.get(node_key) == signature

    def invalidate(self, node_key: str) -> None:
        self._values.pop(node_key, None)
        self._signatures.pop(node_key, None)

    def clear(self) -> None:
        self._values.clear()
        self._signatures.clear()


@dataclass
class RuntimeContext:
    graph: Graph
    configuration: AppConfiguration | None = None
    state: MutableMapping[str, object] = field(default_factory=dict)

    @property
    def enable_memoization(self) -> bool:
        if self.configuration is None:
            return True
        return self.configuration.performance.enable_memoization


class GraphScheduler:
    def __init__(
        self,
        graph: Graph,
        *,
        node_registry: NodeRegistry | None = None,
        cache: ExecutionCache | None = None,
    ) -> None:
        self.graph = graph
        self.registry = node_registry or registry
        self.cache = cache or ExecutionCache()

    def evaluate(
        self,
        *,
        targets: Iterable[str] | None = None,
        context: RuntimeContext | None = None,
        force: bool = False,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> dict[str, Mapping[str, object]]:
        if context is None:
            context = RuntimeContext(self.graph)
        if targets is None:
            result_nodes = list(self.graph.nodes)
        else:
            result_nodes = [node for node in targets if node in self.graph.nodes]
        if not result_nodes:
            return {}

        execution_order = tuple(self.graph.topological_order(limit_to=result_nodes))
        total = len(execution_order)
        results: dict[str, Mapping[str, object]] = {}

        if progress is not None:
            progress(0, total, "")

        for index, node_key in enumerate(execution_order, start=1):
            node = self.graph.nodes[node_key]
            input_values = self._collect_inputs(node_key, results)
            signature = _make_signature(node, input_values)
            use_cache = (
                not force
                and context.enable_memoization
                and node_key not in self.graph.dirty
                and self.cache.is_valid(node_key, signature)
            )

            if use_cache:
                outputs = self.cache.get(node_key)
                if outputs is None:
                    raise SchedulerError(f"Cache miss for node '{node_key}'")
            else:
                handler = self.registry.get(node.type).handler
                try:
                    outputs = handler(node, input_values, context)
                except Exception as exc:
                    raise SchedulerError(f"Node '{node.key}' failed: {exc}") from exc
                if not isinstance(outputs, Mapping):
                    raise SchedulerError(
                        f"Node '{node.key}' produced non-mapping outputs of type {type(outputs)!r}"
                    )
                if context.enable_memoization:
                    self.cache.store(node_key, signature, outputs)
            results[node_key] = outputs
            self.graph.clear_dirty(node_key)
            if progress is not None:
                progress(index, total, node_key)

        return {node: results[node] for node in result_nodes if node in results}

    def _collect_inputs(
        self,
        node_key: str,
        results: Mapping[str, Mapping[str, object]],
    ) -> dict[str, object]:
        inputs: dict[str, object] = {}
        for port_name, connection in self.graph.inputs_for(node_key).items():
            cached_outputs = self.cache.get(connection.source_node)
            current_outputs = results.get(connection.source_node)
            source_outputs = current_outputs or cached_outputs
            if source_outputs is None:
                raise SchedulerError(
                    f"Missing outputs for '{connection.source_node}' required by '{node_key}'"
                )
            if connection.source_port not in source_outputs:
                message = (
                    f"Node '{connection.source_node}' "
                    f"does not provide port '{connection.source_port}'"
                )
                raise SchedulerError(message)
            inputs[port_name] = source_outputs[connection.source_port]
        return inputs


def _make_signature(node: Node, inputs: Mapping[str, object]) -> str:
    payload = {
        "node": node.key,
        "type": node.type,
        "parameters": _normalise_value(node.parameters),
        "inputs": _normalise_value(inputs),
    }
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _normalise_value(value: object) -> object:
    if isinstance(value, (str | int | float | bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {
            str(key): _normalise_value(val)
            for key, val in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, list | tuple | set):
        return [_normalise_value(item) for item in value]
    if isinstance(value, np.ndarray):
        return {
            "__ndarray__": True,
            "shape": value.shape,
            "dtype": str(value.dtype),
            "digest": hashlib.sha1(value.tobytes()).hexdigest(),
        }
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return {"__object__": value.__class__.__name__, "data": _normalise_value(value.__dict__)}
    return repr(value)
