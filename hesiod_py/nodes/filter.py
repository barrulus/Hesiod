"""Filtering nodes for heightmaps."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray

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

__all__ = ["register_filter_nodes"]


_FILTER_METADATA = {
    "filter.box_blur": NodeMetadata(
        type="filter.box_blur",
        label="Box Blur",
        category="Filter",
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
                description="Blurred heightmap",
            ),
        ),
        parameters=(
            ParameterSpec(
                "kernel_size",
                "int",
                3,
                "Odd-sized kernel width/height",
            ),
        ),
        description="Apply a mean blur using a square kernel.",
        tags=("filter", "heightmap"),
    ),
    "filter.gaussian_blur": NodeMetadata(
        type="filter.gaussian_blur",
        label="Gaussian Blur",
        category="Filter",
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
                description="Blurred heightmap",
            ),
        ),
        parameters=(
            ParameterSpec(
                "kernel_size",
                "int",
                5,
                "Odd-sized kernel width/height",
            ),
            ParameterSpec(
                "sigma",
                "float",
                None,
                "Gaussian standard deviation",
            ),
        ),
        description="Apply a Gaussian blur to smooth the heightmap.",
        tags=("filter", "heightmap"),
    ),
}


def register_filter_nodes(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "filter.box_blur",
        _box_blur,
        description="Apply a mean blur using a square kernel",
        metadata=_FILTER_METADATA["filter.box_blur"],
    )
    target.register(
        "filter.gaussian_blur",
        _gaussian_blur,
        description="Apply a Gaussian blur",
        metadata=_FILTER_METADATA["filter.gaussian_blur"],
    )


def _expect_heightmap(value: object, node: Node) -> HeightMap:
    if isinstance(value, HeightMap):
        return value
    message = f"Node '{node.key}' expected a HeightMap input, " f"received {type(value)!r}"
    raise TypeError(message)


def _sliding_window_mean(
    data: NDArray[np.float32],
    kernel: NDArray[np.float32],
) -> NDArray[np.float32]:
    from numpy.lib.stride_tricks import sliding_window_view

    view = sliding_window_view(data, kernel.shape)
    weighted = view * kernel
    summed: NDArray[np.float32] = weighted.sum(axis=(-1, -2)).astype(np.float32, copy=False)
    return summed


def _normalize_kernel(kernel: NDArray[np.float32]) -> NDArray[np.float32]:
    kernel = kernel.astype(np.float32)
    total = float(kernel.sum())
    if np.isclose(total, 0.0):
        raise ValueError("Filter kernel must have non-zero sum")
    return kernel / total


def _reflect_pad(data: NDArray[np.float32], pad: int) -> NDArray[np.float32]:
    if pad == 0:
        return data
    padded = np.pad(data, pad_width=pad, mode="reflect")
    return padded.astype(np.float32, copy=False)


def _box_blur(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = _expect_heightmap(inputs.get("source"), node)
    kernel_size = int(node.parameters.get("kernel_size", 3))
    if kernel_size <= 0 or kernel_size % 2 == 0:
        raise ValueError("filter.box_blur requires a positive odd kernel_size")

    pad = kernel_size // 2
    kernel = np.ones((kernel_size, kernel_size), dtype=np.float32)
    kernel = _normalize_kernel(kernel)
    padded = _reflect_pad(source.data.astype(np.float32, copy=False), pad)
    data = _sliding_window_mean(padded, kernel)
    blurred = HeightMap(data=data, bounds=source.bounds, metadata=dict(source.metadata))
    blurred.metadata.setdefault("filter", {})
    blurred.metadata["filter"].update({"mode": "box", "kernel_size": kernel_size})
    return {"heightmap": blurred}


def _gaussian_kernel(size: int, sigma: float) -> NDArray[np.float32]:
    radius = size // 2
    x = np.arange(-radius, radius + 1)
    y = np.arange(-radius, radius + 1)
    xx, yy = np.meshgrid(x, y)
    kernel = np.exp(-(xx**2 + yy**2) / (2 * sigma**2)).astype(np.float32)
    return _normalize_kernel(kernel)


def _gaussian_blur(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = _expect_heightmap(inputs.get("source"), node)
    kernel_size = int(node.parameters.get("kernel_size", 5))
    if kernel_size <= 0 or kernel_size % 2 == 0:
        raise ValueError("filter.gaussian_blur requires a positive odd kernel_size")
    sigma = float(node.parameters.get("sigma", max(kernel_size / 3.0, 1.0)))
    if sigma <= 0:
        raise ValueError("Gaussian blur requires sigma > 0")

    pad = kernel_size // 2
    kernel = _gaussian_kernel(kernel_size, sigma)
    padded = _reflect_pad(source.data.astype(np.float32, copy=False), pad)
    data = _sliding_window_mean(padded, kernel)
    blurred = HeightMap(data=data, bounds=source.bounds, metadata=dict(source.metadata))
    blurred.metadata.setdefault("filter", {})
    blurred.metadata["filter"].update(
        {"mode": "gaussian", "kernel_size": kernel_size, "sigma": sigma}
    )
    return {"heightmap": blurred}
