"""Blend nodes for combining heightmaps."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from ..core.graph import Node
from ..core.registry import (
    ExecutionContext,
    NodeMetadata,
    NodeRegistry,
    ParameterSpec,
    PortSpec,
    registry,
)
from ..data.structures import HeightMap

__all__ = ["register_blend_nodes"]


_BLEND_METADATA = {
    "blend.linear": NodeMetadata(
        type="blend.linear",
        label="Linear Blend",
        category="Blend",
        inputs=(
            PortSpec(name="foreground", data_type="heightmap", description="Foreground heightmap"),
            PortSpec(name="background", data_type="heightmap", description="Background heightmap"),
        ),
        outputs=(PortSpec(name="heightmap", data_type="heightmap", description="Blended result"),),
        parameters=(
            ParameterSpec(
                "factor",
                "float",
                0.5,
                "Weight of the foreground input (0..1)",
            ),
        ),
        description=(
            "Blend between foreground and background heightmaps using " "linear interpolation."
        ),
        tags=("blend", "heightmap"),
    ),
    "blend.add": NodeMetadata(
        type="blend.add",
        label="Add",
        category="Blend",
        inputs=(
            PortSpec(name="source_a", data_type="heightmap", description="First heightmap"),
            PortSpec(name="source_b", data_type="heightmap", description="Second heightmap"),
        ),
        outputs=(
            PortSpec(name="heightmap", data_type="heightmap", description="Combined heightmap"),
        ),
        parameters=(
            ParameterSpec("scale", "float", 1.0, "Scale applied after addition"),
            ParameterSpec("bias", "float", 0.0, "Bias applied after scaling"),
        ),
        description="Add two heightmaps with optional scale and bias.",
        tags=("blend", "heightmap"),
    ),
}


def register_blend_nodes(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "blend.linear",
        _linear_blend,
        description="Linear blend between foreground and background heightmaps",
        metadata=_BLEND_METADATA["blend.linear"],
    )
    target.register(
        "blend.add",
        _additive_blend,
        description="Add two heightmaps with optional scale and bias",
        metadata=_BLEND_METADATA["blend.add"],
    )


def _expect_heightmap(name: str, value: object, node: Node) -> HeightMap:
    if isinstance(value, HeightMap):
        return value
    message = f"Node '{node.key}' expected '{name}' to be a HeightMap, " f"received {type(value)!r}"
    raise TypeError(message)


def _ensure_same_shape(node: Node, *heightmaps: HeightMap) -> None:
    shapes = {hm.resolution for hm in heightmaps}
    if len(shapes) > 1:
        message = f"Node '{node.key}' requires matching resolutions, " f"received {sorted(shapes)}"
        raise ValueError(message)


def _linear_blend(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    foreground = _expect_heightmap("foreground", inputs.get("foreground"), node)
    background = _expect_heightmap("background", inputs.get("background"), node)
    _ensure_same_shape(node, foreground, background)

    factor = float(node.parameters.get("factor", 0.5))
    factor = float(np.clip(factor, 0.0, 1.0))
    data = (foreground.data * factor) + (background.data * (1.0 - factor))
    blended = HeightMap(
        data=data.astype(np.float32, copy=False),
        bounds=foreground.bounds,
        metadata=dict(foreground.metadata),
    )
    blended.metadata.setdefault("blend", {})
    blended.metadata["blend"]["mode"] = "linear"
    blended.metadata["blend"]["factor"] = factor
    return {"heightmap": blended}


def _additive_blend(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source_a = _expect_heightmap("source_a", inputs.get("source_a"), node)
    source_b = _expect_heightmap("source_b", inputs.get("source_b"), node)
    _ensure_same_shape(node, source_a, source_b)

    scale = float(node.parameters.get("scale", 1.0))
    bias = float(node.parameters.get("bias", 0.0))
    data = (source_a.data + source_b.data) * scale + bias
    blended = HeightMap(
        data=data.astype(np.float32, copy=False),
        bounds=source_a.bounds,
        metadata=dict(source_a.metadata),
    )
    blended.metadata.setdefault("blend", {})
    blended.metadata["blend"].update({"mode": "add", "scale": scale, "bias": bias})
    return {"heightmap": blended}
