"""Project-level container types."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .configuration import AppConfiguration
from .graph import Graph, Node

__all__ = ["Project", "ProjectSerializer", "ProjectError"]


class ProjectError(RuntimeError):
    """Base error for project persistence failures."""


@dataclass
class Project:
    name: str
    graph: Graph
    configuration: AppConfiguration
    assets: dict[str, Path] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def register_asset(self, key: str, path: Path) -> None:
        self.assets[key] = path


class ProjectSerializer:
    VERSION = "1.0"

    @classmethod
    def to_json(cls, project: Project) -> str:
        payload = {
            "version": cls.VERSION,
            "name": project.name,
            "configuration": json.loads(project.configuration.model_dump_json()),
            "graph": cls._graph_to_dict(project.graph),
            "assets": {key: str(value) for key, value in project.assets.items()},
            "metadata": project.metadata,
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def from_json(cls, data: str, configuration: AppConfiguration) -> Project:
        raw = json.loads(data)
        graph = cls._graph_from_dict(raw.get("graph", {}))
        return Project(
            name=raw.get("name", "Untitled"),
            graph=graph,
            configuration=configuration,
            assets={key: Path(value) for key, value in raw.get("assets", {}).items()},
            metadata=raw.get("metadata", {}),
        )

    @staticmethod
    def _graph_to_dict(graph: Graph) -> dict[str, Any]:
        return {
            "name": graph.name,
            "metadata": graph.metadata,
            "nodes": [
                {
                    "key": node.key,
                    "type": node.type,
                    "title": node.title,
                    "parameters": dict(node.parameters),
                    "metadata": dict(node.metadata),
                }
                for node in graph.nodes.values()
            ],
            "connections": {
                node_key: {
                    port: {
                        "source_node": connection.source_node,
                        "source_port": connection.source_port,
                    }
                    for port, connection in graph.inputs_for(node_key).items()
                }
                for node_key in graph.nodes
            },
        }

    @staticmethod
    def _graph_from_dict(payload: Mapping[str, Any]) -> Graph:
        graph = Graph(name=payload.get("name", "Graph"), metadata=payload.get("metadata", {}))
        for node_data in payload.get("nodes", []):
            node = Node(
                key=node_data["key"],
                type=node_data["type"],
                title=node_data.get("title"),
                parameters=dict(node_data.get("parameters", {})),
                metadata=dict(node_data.get("metadata", {})),
            )
            graph.add_node(node)
        for node_key, ports in payload.get("connections", {}).items():
            for port_name, connection in ports.items():
                graph.connect(
                    source_node=connection["source_node"],
                    source_port=connection["source_port"],
                    target_node=node_key,
                    target_port=port_name,
                )
        return graph
