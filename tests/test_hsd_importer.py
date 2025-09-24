from __future__ import annotations

import json
from pathlib import Path

from hesiod_py.core.configuration import AppConfiguration, RuntimePaths
from hesiod_py.io.hsd import LEGACY_NODE_MAP, import_legacy_project


def build_config(tmp_path: Path) -> AppConfiguration:
    return AppConfiguration(
        paths=RuntimePaths(
            project_root=tmp_path,
            cache_dir=tmp_path / "cache",
            asset_dir=tmp_path / "assets",
        )
    )


def test_import_legacy_project(tmp_path: Path) -> None:
    project_payload = {
        "name": "Legacy",
        "graph": {
            "name": "Legacy Graph",
            "nodes": [
                {"id": "A", "type": "ConstantNode", "parameters": {"value": 5}},
                {"id": "B", "type": "AddNode"},
                {"id": "C", "type": "UnsupportedNode"},
            ],
            "connections": {
                "b": {
                    "lhs": {"source_node": "A", "source_port": "output"},
                    "rhs": {"source_node": "C", "source_port": "output"},
                }
            },
        },
    }
    path = tmp_path / "sample.hsd"
    path.write_text(json.dumps(project_payload), encoding="utf-8")

    report = import_legacy_project(path, build_config(tmp_path))

    assert report.project.graph.nodes["a"].type == LEGACY_NODE_MAP["ConstantNode"]
    assert "UnsupportedNode" in report.unsupported_nodes
    assert report.project.name == "Legacy"
