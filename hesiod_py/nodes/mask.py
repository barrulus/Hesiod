"""Masking nodes for heightmaps."""

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

__all__ = ["register_mask_nodes"]


_MASK_METADATA = {
    "mask.threshold": NodeMetadata(
        type="mask.threshold",
        label="Threshold",
        category="Mask",
        inputs=(
            PortSpec(
                name="source",
                data_type="heightmap",
                description="Source heightmap",
            ),
        ),
        outputs=(
            PortSpec(
                name="mask",
                data_type="mask",
                description="Resulting mask",
            ),
        ),
        parameters=(
            ParameterSpec("threshold", "float", 0.5, "Threshold value"),
            ParameterSpec(
                "mode",
                "enum",
                "greater",
                "Comparison mode",
                choices=("greater", "greater_equal", "less", "less_equal"),
            ),
        ),
        description="Create a binary mask by thresholding a heightmap.",
        tags=("mask", "heightmap"),
    ),
    "mask.invert": NodeMetadata(
        type="mask.invert",
        label="Invert",
        category="Mask",
        inputs=(
            PortSpec(
                name="mask",
                data_type="mask",
                description="Mask to invert",
            ),
        ),
        outputs=(
            PortSpec(
                name="mask",
                data_type="mask",
                description="Inverted mask",
            ),
        ),
        parameters=(),
        description="Invert a binary mask.",
        tags=("mask",),
    ),
    "mask.apply": NodeMetadata(
        type="mask.apply",
        label="Apply Mask",
        category="Mask",
        inputs=(
            PortSpec(
                name="source",
                data_type="heightmap",
                description="Heightmap to mask",
            ),
            PortSpec(
                name="mask",
                data_type="mask",
                description="Mask controlling blending",
            ),
        ),
        outputs=(
            PortSpec(
                name="heightmap",
                data_type="heightmap",
                description="Masked heightmap",
            ),
        ),
        parameters=(ParameterSpec("fill", "float", 0.0, "Value used where mask is zero"),),
        description="Apply a mask to a heightmap, filling masked areas with a value.",
        tags=("mask", "heightmap"),
    ),
}


def register_mask_nodes(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "mask.threshold",
        _threshold_mask,
        description="Generate a binary mask using threshold",
        metadata=_MASK_METADATA["mask.threshold"],
    )
    target.register(
        "mask.invert",
        _invert_mask,
        description="Invert a mask",
        metadata=_MASK_METADATA["mask.invert"],
    )
    target.register(
        "mask.apply",
        _apply_mask,
        description="Apply a mask to a heightmap with optional fill value",
        metadata=_MASK_METADATA["mask.apply"],
    )


def _expect_heightmap(name: str, value: object, node: Node) -> HeightMap:
    if isinstance(value, HeightMap):
        return value
    message = f"Node '{node.key}' expected '{name}' to be a HeightMap, " f"received {type(value)!r}"
    raise TypeError(message)


def _threshold_mask(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = _expect_heightmap("source", inputs.get("source"), node)
    threshold = float(node.parameters.get("threshold", 0.5))
    mode = str(node.parameters.get("mode", "greater")).lower()
    if mode not in {"greater", "greater_equal", "less", "less_equal"}:
        raise ValueError(
            "mask.threshold mode must be one of greater, greater_equal, less, less_equal"
        )

    if mode == "greater":
        mask = source.data > threshold
    elif mode == "greater_equal":
        mask = source.data >= threshold
    elif mode == "less":
        mask = source.data < threshold
    else:
        mask = source.data <= threshold

    mask_data = mask.astype(np.float32)
    masked = HeightMap(data=mask_data, bounds=source.bounds, metadata=dict(source.metadata))
    masked.metadata.setdefault("mask", {})
    masked.metadata["mask"].update({"mode": mode, "threshold": threshold})
    return {"mask": masked}


def _invert_mask(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    mask = _expect_heightmap("mask", inputs.get("mask"), node)
    inverted = HeightMap(
        data=(1.0 - mask.data).astype(np.float32, copy=False),
        bounds=mask.bounds,
        metadata=dict(mask.metadata),
    )
    inverted.metadata.setdefault("mask", {})
    inverted.metadata["mask"].update({"inverted": True})
    return {"mask": inverted}


def _apply_mask(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = _expect_heightmap("source", inputs.get("source"), node)
    mask = _expect_heightmap("mask", inputs.get("mask"), node)
    _ensure_same_shape(node, source, mask)

    fill_value = float(node.parameters.get("fill", 0.0))
    mask_data = np.clip(mask.data, 0.0, 1.0)
    data = source.data * mask_data + fill_value * (1.0 - mask_data)
    masked = HeightMap(
        data=data.astype(np.float32, copy=False),
        bounds=source.bounds,
        metadata=dict(source.metadata),
    )
    masked.metadata.setdefault("mask", {})
    masked.metadata["mask"].update({"applied": True, "fill": fill_value})
    return {"heightmap": masked}


def _ensure_same_shape(node: Node, *heightmaps: HeightMap) -> None:
    shapes = {hm.resolution for hm in heightmaps}
    if len(shapes) > 1:
        message = f"Node '{node.key}' requires matching resolutions, " f"received {sorted(shapes)}"
        raise ValueError(message)
