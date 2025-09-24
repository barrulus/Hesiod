"""Importer for legacy .hsd project files."""

from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from loguru import logger

from ..core.configuration import AppConfiguration
from ..core.graph import Graph, Node
from ..core.project import Project

__all__ = ["LegacyImportReport", "import_legacy_project", "LEGACY_NODE_MAP"]

LEGACY_NODE_MAP: dict[str, str] = {
    "ConstantNode": "primitives.constant",
    "AddNode": "math.add",
    "MultiplyNode": "math.multiply",
}


@dataclass
class LegacyImportReport:
    project: Project
    unsupported_nodes: list[str] = field(default_factory=list)


class LegacyImportError(RuntimeError):
    """Raised when an .hsd file cannot be converted."""


def import_legacy_project(
    path: Path,
    configuration: AppConfiguration,
    *,
    node_overrides: Mapping[str, str] | None = None,
) -> LegacyImportReport:
    if not path.exists():
        raise LegacyImportError(f"Legacy project not found: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LegacyImportError(f"Failed to parse legacy project: {path}") from exc

    graph_payload = payload.get("graph", payload)
    nodes_payload = cast(Sequence[Mapping[str, object]], graph_payload.get("nodes", []))
    connections_payload = cast(
        Mapping[str, Mapping[str, Mapping[str, str]]],
        graph_payload.get("connections", {}),
    )

    graph = Graph(name=graph_payload.get("name", "Legacy Graph"))
    unsupported: list[str] = []

    remap: MutableMapping[str, str] = dict(LEGACY_NODE_MAP)
    if node_overrides:
        remap.update({legacy: target for legacy, target in node_overrides.items()})

    for node_data in nodes_payload:
        legacy_type = str(node_data.get("type", "Unknown"))
        node_type = remap.get(legacy_type)
        if node_type is None:
            unsupported.append(legacy_type)
            node_type = legacy_type
            logger.warning("Unsupported legacy node encountered: {}", legacy_type)

        raw_key = node_data.get("id") or node_data.get("key") or node_data.get("name", legacy_type)
        node_key = str(raw_key).lower()
        node = Node(
            key=node_key,
            type=node_type,
            title=str(node_data.get("name", legacy_type)),
            parameters=_coerce_parameters(node_data.get("parameters", {})),
            metadata={"legacy_type": legacy_type},
        )
        graph.add_node(node)

    for target_key, ports in connections_payload.items():
        for port_name, connection in ports.items():
            graph.connect(
                source_node=str(connection["source_node"]).lower(),
                source_port=str(connection.get("source_port", "output")),
                target_node=str(target_key).lower(),
                target_port=str(port_name),
            )

    project = Project(
        name=payload.get("name", graph.name),
        graph=graph,
        configuration=configuration,
        metadata=payload.get("metadata", {}),
    )

    return LegacyImportReport(project=project, unsupported_nodes=unsupported)


def _coerce_parameters(raw: object) -> dict[str, object]:
    if isinstance(raw, dict):
        return {str(key): value for key, value in raw.items()}
    return {}
