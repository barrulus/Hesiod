from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from hesiod_py.core.graph import Node
from hesiod_py.core.registry import NodeRegistry
from hesiod_py.data.structures import HeightMap
from hesiod_py.nodes.image_io import register_image_io_nodes
from PIL import Image


class _DummyContext:
    def __init__(self) -> None:
        self.state: dict[str, object] = {}


@pytest.fixture()
def registry() -> NodeRegistry:
    reg = NodeRegistry()
    register_image_io_nodes(reg)
    return reg


@pytest.fixture()
def context() -> _DummyContext:
    return _DummyContext()


def test_export_and_import_heightmap(
    tmp_path: Path, registry: NodeRegistry, context: _DummyContext
) -> None:
    handler_export = registry.get("export.heightmap").handler
    handler_import = registry.get("import.heightmap").handler

    data = np.array([[0.1, 0.5], [0.8, 1.0]], dtype=np.float32)
    hm = HeightMap(data=data, bounds=(0, 2, 0, 2))
    path = tmp_path / "heightmap.png"

    node_export = Node(
        key="export",
        type="export.heightmap",
        parameters={"path": str(path), "min": 0.0, "max": 1.0},
    )
    handler_export(node_export, {"source": hm}, context)

    node_import = Node(
        key="import", type="import.heightmap", parameters={"path": str(path), "normalize": True}
    )
    result = handler_import(node_import, {}, context)
    imported = result["heightmap"].data
    np.testing.assert_allclose(imported, data, atol=1 / 255.0)


def test_export_normal_map(tmp_path: Path, registry: NodeRegistry, context: _DummyContext) -> None:
    handler = registry.get("export.normal_map").handler
    data = np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float32)
    hm = HeightMap(data=data, bounds=(0, 2, 0, 2))
    path = tmp_path / "normal.png"
    node = Node(
        key="normal", type="export.normal_map", parameters={"path": str(path), "strength": 2.0}
    )
    handler(node, {"source": hm}, context)

    image = Image.open(path)
    assert image.mode == "RGB"
    assert image.size == (2, 2)


def test_texture_import_export_roundtrip(
    tmp_path: Path, registry: NodeRegistry, context: _DummyContext
) -> None:
    handler_import = registry.get("import.texture").handler
    handler_export = registry.get("export.texture").handler

    src_path = tmp_path / "texture.png"
    texture_image = Image.new("RGB", (2, 2), color=(255, 0, 0))
    texture_image.save(src_path)

    node_import = Node(
        key="import", type="import.texture", parameters={"path": str(src_path), "mode": "RGB"}
    )
    result = handler_import(node_import, {}, context)
    texture = result["texture"]
    assert texture.shape == (2, 2, 3)
    np.testing.assert_allclose(texture[0, 0], np.array([1.0, 0.0, 0.0], dtype=np.float32))

    out_path = tmp_path / "texture_out.png"
    node_export = Node(
        key="export", type="export.texture", parameters={"path": str(out_path), "mode": "RGB"}
    )
    handler_export(node_export, {"texture": texture}, context)

    exported = Image.open(out_path)
    assert exported.mode == "RGB"
    assert exported.size == (2, 2)
