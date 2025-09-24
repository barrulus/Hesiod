"""Transform nodes for manipulating heightmaps."""

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

__all__ = ["register_transform_nodes"]


_TRANSFORM_METADATA = {
    "transform.scale_bias": NodeMetadata(
        type="transform.scale_bias",
        label="Scale & Bias",
        category="Transform",
        inputs=(
            PortSpec(
                name="source",
                data_type="heightmap",
                description="Input heightmap",
            ),
        ),
        outputs=(
            PortSpec(
                name="heightmap",
                data_type="heightmap",
                description="Scaled result",
            ),
        ),
        parameters=(
            ParameterSpec("scale", "float", 1.0, "Multiplier applied to the input"),
            ParameterSpec("bias", "float", 0.0, "Bias added after scaling"),
        ),
        description="Apply a linear scale and bias to a heightmap.",
        tags=("transform", "heightmap"),
    ),
    "transform.normalize": NodeMetadata(
        type="transform.normalize",
        label="Normalize",
        category="Transform",
        inputs=(
            PortSpec(
                name="source",
                data_type="heightmap",
                description="Input heightmap",
            ),
        ),
        outputs=(
            PortSpec(
                name="heightmap",
                data_type="heightmap",
                description="Normalized heightmap",
            ),
        ),
        parameters=(
            ParameterSpec("min", "float", 0.0, "Target minimum"),
            ParameterSpec("max", "float", 1.0, "Target maximum"),
        ),
        description="Normalize a heightmap into a specified range.",
        tags=("transform", "heightmap"),
    ),
}


def register_transform_nodes(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "transform.scale_bias",
        _scale_bias,
        description="Apply scale and bias to a heightmap",
        metadata=_TRANSFORM_METADATA["transform.scale_bias"],
    )
    target.register(
        "transform.normalize",
        _normalize,
        description="Normalize heightmap to [min, max] range",
        metadata=_TRANSFORM_METADATA["transform.normalize"],
    )


def _expect_heightmap(value: object, node: Node) -> HeightMap:
    if isinstance(value, HeightMap):
        return value
    message = f"Node '{node.key}' expected HeightMap input, " f"received {type(value)!r}"
    raise TypeError(message)


def _scale_bias(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = inputs.get("source")
    if source is None:
        raise ValueError("transform.scale_bias requires 'source' input")
    heightmap = _expect_heightmap(source, node)

    scale = float(node.parameters.get("scale", 1.0))
    bias = float(node.parameters.get("bias", 0.0))
    data = (heightmap.data * scale) + bias
    transformed = HeightMap(
        data=data.astype(np.float32, copy=False),
        bounds=heightmap.bounds,
        metadata=dict(heightmap.metadata),
    )
    transformed.metadata.setdefault("transform", {})
    transformed.metadata["transform"].update({"scale": scale, "bias": bias})
    return {"heightmap": transformed}


def _normalize(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = inputs.get("source")
    if source is None:
        raise ValueError("transform.normalize requires 'source' input")
    heightmap = _expect_heightmap(source, node)

    target_min = float(node.parameters.get("min", 0.0))
    target_max = float(node.parameters.get("max", 1.0))
    if target_max <= target_min:
        raise ValueError("Normalize node requires max > min")

    data = heightmap.data.astype(np.float32, copy=False)
    current_min = float(data.min())
    current_max = float(data.max())
    if np.isclose(current_max, current_min):
        normalized_data = np.full_like(data, fill_value=target_min)
    else:
        normalized_data = (data - current_min) / (current_max - current_min)
        normalized_data = normalized_data * (target_max - target_min) + target_min

    normalized = HeightMap(
        data=normalized_data.astype(np.float32, copy=False),
        bounds=heightmap.bounds,
        metadata=dict(heightmap.metadata),
    )
    normalized.metadata.setdefault("transform", {})
    normalized.metadata["transform"].update(
        {
            "normalized": True,
            "target_min": target_min,
            "target_max": target_max,
        }
    )
    return {"heightmap": normalized}
