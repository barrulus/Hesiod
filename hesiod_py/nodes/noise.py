"""Noise node implementations using numpy."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

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

__all__ = ["register_noise_nodes"]


@dataclass(frozen=True, slots=True)
class _NoiseParameters:
    width: int
    height: int
    low: float
    high: float
    seed: int


_NOISE_METADATA = {
    "noise.uniform": NodeMetadata(
        type="noise.uniform",
        label="Uniform Noise",
        category="Noise",
        inputs=(),
        outputs=(PortSpec(name="heightmap", data_type="heightmap", description="Generated noise"),),
        parameters=(
            ParameterSpec("width", "int", 256, "Width in pixels"),
            ParameterSpec("height", "int", 256, "Height in pixels"),
            ParameterSpec("low", "float", 0.0, "Lower bound"),
            ParameterSpec("high", "float", 1.0, "Upper bound"),
            ParameterSpec("seed", "int", 0, "Random generator seed"),
        ),
        description="Generate uniform random noise as a heightmap.",
        tags=("noise", "generator"),
    ),
    "noise.gaussian": NodeMetadata(
        type="noise.gaussian",
        label="Gaussian Noise",
        category="Noise",
        inputs=(),
        outputs=(PortSpec(name="heightmap", data_type="heightmap", description="Gaussian noise"),),
        parameters=(
            ParameterSpec("width", "int", 256, "Width in pixels"),
            ParameterSpec("height", "int", 256, "Height in pixels"),
            ParameterSpec("low", "float", 0.0, "Lower clamp"),
            ParameterSpec("high", "float", 1.0, "Upper clamp"),
            ParameterSpec("seed", "int", 0, "Random generator seed"),
            ParameterSpec("mean", "float", None, "Distribution mean"),
            ParameterSpec("std_dev", "float", None, "Standard deviation"),
        ),
        description="Generate Gaussian noise with optional mean and deviation.",
        tags=("noise", "generator"),
    ),
}


def register_noise_nodes(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "noise.uniform",
        _uniform_noise,
        description="Uniform random heightmap noise",
        metadata=_NOISE_METADATA["noise.uniform"],
    )
    target.register(
        "noise.gaussian",
        _gaussian_noise,
        description="Gaussian random heightmap noise",
        metadata=_NOISE_METADATA["noise.gaussian"],
    )


def _parse_params(node: Node) -> _NoiseParameters:
    width = int(node.parameters.get("width", 256))
    height = int(node.parameters.get("height", 256))
    low = float(node.parameters.get("low", 0.0))
    high = float(node.parameters.get("high", 1.0))
    seed = int(node.parameters.get("seed", 0))
    if width <= 0 or height <= 0:
        raise ValueError("Noise nodes require positive width and height")
    if high < low:
        raise ValueError("Noise range 'high' must be greater than or equal to 'low'")
    return _NoiseParameters(width=width, height=height, low=low, high=high, seed=seed)


def _uniform_noise(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    params = _parse_params(node)
    if np.isclose(params.high, params.low):
        data = np.full((params.height, params.width), fill_value=params.low, dtype=np.float32)
    else:
        generator = np.random.default_rng(seed=params.seed)
        data = generator.uniform(
            low=params.low,
            high=params.high,
            size=(params.height, params.width),
        ).astype(np.float32)
    heightmap = HeightMap(data=data, bounds=(0.0, float(params.width), 0.0, float(params.height)))
    return {"heightmap": heightmap}


def _gaussian_noise(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    params = _parse_params(node)
    mean = float(node.parameters.get("mean", (params.high + params.low) / 2.0))
    std_default = (params.high - params.low) / 6.0
    std_dev = float(node.parameters.get("std_dev", std_default if std_default > 0 else 1.0))
    if std_dev <= 0:
        raise ValueError("Noise nodes require a positive std_dev")

    if np.isclose(params.high, params.low):
        data = np.full((params.height, params.width), fill_value=params.low, dtype=np.float32)
    else:
        generator = np.random.default_rng(seed=params.seed)
        data = generator.normal(
            loc=mean,
            scale=std_dev,
            size=(params.height, params.width),
        ).astype(np.float32)
        data = np.clip(data, params.low, params.high)

    heightmap = HeightMap(data=data, bounds=(0.0, float(params.width), 0.0, float(params.height)))
    return {"heightmap": heightmap}
