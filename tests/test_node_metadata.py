from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from hesiod_py.core.graph import Node
from hesiod_py.core.registry import (
    ExecutionContext,
    NodeMetadata,
    NodeRegistry,
    ParameterSpec,
    PortSpec,
    RegistryError,
)
from hesiod_py.nodes.primitives import register_primitives


def test_describe_returns_metadata() -> None:
    registry = NodeRegistry()
    register_primitives(registry)

    metadata = registry.describe("primitives.constant")
    assert isinstance(metadata, NodeMetadata)
    assert metadata.label == "Constant"
    assert metadata.outputs[0].name == "output"
    assert metadata.outputs[0].data_type == "scalar"
    assert metadata.parameters[0].default == 0.0


def test_metadata_iterator() -> None:
    registry = NodeRegistry()
    register_primitives(registry)
    specs = {spec.type for spec in registry.metadata()}
    assert "primitives.constant" in specs


def test_missing_metadata_raises() -> None:
    registry = NodeRegistry()

    def handler(
        node: Node,
        inputs: Mapping[str, Any],
        context: ExecutionContext,
    ) -> Mapping[str, Any]:
        return {}

    registry.register("custom.node", handler)
    with pytest.raises(RegistryError):
        registry.describe("custom.node")


def test_metadata_to_dict() -> None:
    meta = NodeMetadata(
        type="example",
        label="Example",
        category="Test",
        inputs=(PortSpec(name="a", data_type="scalar"),),
        outputs=(PortSpec(name="b", data_type="scalar"),),
        parameters=(ParameterSpec(name="gain", param_type="float", default=1.0),),
        description="Example node",
        tags=("example",),
    )
    data = meta.to_dict()
    assert data["type"] == "example"
    assert data["parameters"][0]["default"] == 1.0
