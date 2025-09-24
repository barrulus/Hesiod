"""Image import/export nodes using Pillow."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
from PIL import Image

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

__all__ = ["register_image_io_nodes"]


class ImageIONodeError(RuntimeError):
    """Raised when image import or export fails."""


_SUPPORTED_TEXTURE_MODES = {"L", "RGB", "RGBA"}
_TEXTURE_MODE_CHOICES = tuple(sorted(_SUPPORTED_TEXTURE_MODES))


_IMAGE_METADATA = {
    "import.heightmap": NodeMetadata(
        type="import.heightmap",
        label="Import Heightmap",
        category="I/O",
        inputs=(),
        outputs=(
            PortSpec(
                name="heightmap",
                data_type="heightmap",
                description="Imported heightmap",
            ),
        ),
        parameters=(
            ParameterSpec("path", "path", None, "Image path"),
            ParameterSpec("normalize", "bool", True, "Normalize to [0,1]"),
            ParameterSpec("scale", "float", 1.0, "Scale after normalization"),
        ),
        description="Load a grayscale image as a heightmap.",
        tags=("import", "heightmap"),
    ),
    "export.heightmap": NodeMetadata(
        type="export.heightmap",
        label="Export Heightmap",
        category="I/O",
        inputs=(
            PortSpec(
                name="source",
                data_type="heightmap",
                description="Heightmap to export",
            ),
        ),
        outputs=(PortSpec(name="path", data_type="path", description="Output path"),),
        parameters=(
            ParameterSpec("path", "path", None, "Destination path"),
            ParameterSpec("min", "float", None, "Clamp minimum"),
            ParameterSpec("max", "float", None, "Clamp maximum"),
            ParameterSpec("mkdirs", "bool", True, "Create folders"),
        ),
        description="Save a heightmap to an 8-bit grayscale image.",
        tags=("export", "heightmap"),
    ),
    "export.normal_map": NodeMetadata(
        type="export.normal_map",
        label="Export Normal Map",
        category="I/O",
        inputs=(
            PortSpec(
                name="source",
                data_type="heightmap",
                description="Heightmap to convert",
            ),
        ),
        outputs=(PortSpec(name="path", data_type="path", description="Output path"),),
        parameters=(
            ParameterSpec("path", "path", None, "Destination path"),
            ParameterSpec("strength", "float", 1.0, "Gradient strength"),
            ParameterSpec("mkdirs", "bool", True, "Create folders"),
        ),
        description="Generate a tangent-space normal map from a heightmap.",
        tags=("export", "normal-map"),
    ),
    "import.texture": NodeMetadata(
        type="import.texture",
        label="Import Texture",
        category="I/O",
        inputs=(),
        outputs=(
            PortSpec(name="texture", data_type="texture", description="Texture tensor"),
            PortSpec(name="metadata", data_type="dict", description="Texture metadata"),
        ),
        parameters=(
            ParameterSpec("path", "path", None, "Texture path"),
            ParameterSpec(
                "mode",
                "enum",
                "RGB",
                "Color space",
                choices=_TEXTURE_MODE_CHOICES,
            ),
        ),
        description="Load a texture image into a float tensor.",
        tags=("import", "texture"),
    ),
    "export.texture": NodeMetadata(
        type="export.texture",
        label="Export Texture",
        category="I/O",
        inputs=(
            PortSpec(
                name="texture",
                data_type="texture",
                description="Texture tensor to export",
            ),
        ),
        outputs=(PortSpec(name="path", data_type="path", description="Output path"),),
        parameters=(
            ParameterSpec("path", "path", None, "Destination path"),
            ParameterSpec(
                "mode",
                "enum",
                "RGB",
                "Preferred color mode",
                choices=_TEXTURE_MODE_CHOICES,
            ),
            ParameterSpec("mkdirs", "bool", True, "Create folders"),
        ),
        description="Write a texture tensor to an image file.",
        tags=("export", "texture"),
    ),
}


def register_image_io_nodes(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "import.heightmap",
        _import_heightmap,
        description="Import grayscale image as heightmap",
        metadata=_IMAGE_METADATA["import.heightmap"],
    )
    target.register(
        "export.heightmap",
        _export_heightmap,
        description="Export heightmap to grayscale image",
        metadata=_IMAGE_METADATA["export.heightmap"],
    )
    target.register(
        "export.normal_map",
        _export_normal_map,
        description="Export heightmap as tangent-space normal map",
        metadata=_IMAGE_METADATA["export.normal_map"],
    )
    target.register(
        "import.texture",
        _import_texture,
        description="Import texture image as float tensor",
        metadata=_IMAGE_METADATA["import.texture"],
    )
    target.register(
        "export.texture",
        _export_texture,
        description="Export texture tensor to image",
        metadata=_IMAGE_METADATA["export.texture"],
    )


def _require_path(node: Node) -> Path:
    raw_path = node.parameters.get("path")
    if not raw_path:
        raise ImageIONodeError(f"Node '{node.key}' requires a 'path' parameter")
    return Path(str(raw_path))


def _import_heightmap(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    path = _require_path(node)
    normalize = bool(node.parameters.get("normalize", True))
    scale = float(node.parameters.get("scale", 1.0))

    try:
        image = Image.open(path).convert("F")
    except OSError as exc:
        raise ImageIONodeError(f"Failed to read heightmap image: {path}") from exc

    data = np.array(image, dtype=np.float32, copy=True)
    if normalize:
        data /= 255.0
    if not np.isclose(scale, 1.0):
        data *= scale

    heightmap = HeightMap(
        data=data,
        bounds=(0.0, float(image.width), 0.0, float(image.height)),
        metadata={"source": str(path)},
    )
    return {"heightmap": heightmap}


def _export_heightmap(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = inputs.get("source")
    if not isinstance(source, HeightMap):
        raise ImageIONodeError(f"Node '{node.key}' expected 'source' HeightMap input")

    path = _require_path(node)
    min_value = node.parameters.get("min")
    max_value = node.parameters.get("max")
    mkdirs = bool(node.parameters.get("mkdirs", True))

    data = source.data.astype(np.float32, copy=False)
    lower = float(min_value) if min_value is not None else float(np.min(data))
    upper = float(max_value) if max_value is not None else float(np.max(data))
    if np.isclose(upper, lower):
        upper = lower + 1.0

    scaled = np.clip((data - lower) / (upper - lower), 0.0, 1.0)
    image = Image.fromarray((scaled * 255.0).astype(np.uint8), mode="L")

    if mkdirs:
        path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {"path": str(path)}


def _export_normal_map(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    source = inputs.get("source")
    if not isinstance(source, HeightMap):
        raise ImageIONodeError(f"Node '{node.key}' expected 'source' HeightMap input")

    path = _require_path(node)
    strength = float(node.parameters.get("strength", 1.0))
    mkdirs = bool(node.parameters.get("mkdirs", True))

    data = source.data.astype(np.float32, copy=False)
    gy, gx = np.gradient(data * strength)
    gz = np.ones_like(data)

    normals = np.stack((-gx, -gy, gz), axis=-1)
    magnitude = np.linalg.norm(normals, axis=-1, keepdims=True)
    magnitude = np.clip(magnitude, 1e-8, None)
    normals /= magnitude
    rgb = ((normals * 0.5) + 0.5) * 255.0
    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")

    if mkdirs:
        path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {"path": str(path)}


def _import_texture(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    path = _require_path(node)
    mode = str(node.parameters.get("mode", "RGB")).upper()
    if mode not in _SUPPORTED_TEXTURE_MODES:
        raise ImageIONodeError(f"Unsupported texture mode '{mode}' requested")

    try:
        image = Image.open(path).convert(mode)
    except OSError as exc:
        raise ImageIONodeError(f"Failed to read texture image: {path}") from exc

    data = np.asarray(image, dtype=np.float32) / 255.0
    return {
        "texture": data,
        "metadata": {
            "mode": mode,
            "size": image.size,
            "source": str(path),
        },
    }


def _export_texture(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    texture = inputs.get("texture")
    if texture is None:
        raise ImageIONodeError(f"Node '{node.key}' expected 'texture' input")

    path = _require_path(node)
    mkdirs = bool(node.parameters.get("mkdirs", True))
    requested_mode = str(node.parameters.get("mode", "RGB")).upper()
    if requested_mode not in _SUPPORTED_TEXTURE_MODES:
        raise ImageIONodeError(f"Unsupported export mode '{requested_mode}'")

    array = np.asarray(texture)
    if array.ndim == 2:
        target_mode = "L"
        array = np.expand_dims(array, axis=-1)
    elif array.ndim != 3:
        raise ImageIONodeError("Texture array must be 2D or 3D")
    else:
        if array.shape[-1] == 4:
            target_mode = "RGBA"
        elif array.shape[-1] == 3:
            target_mode = "RGB"
        elif array.shape[-1] == 1:
            target_mode = "L"
        else:
            raise ImageIONodeError("Texture channel count must be 1, 3, or 4")

    if target_mode not in {requested_mode, "RGBA", "RGB", "L"}:
        message = (
            "Computed texture mode "
            f"'{target_mode}' is incompatible with requested '{requested_mode}'"
        )
        raise ImageIONodeError(message)

    normalized = np.clip(array, 0.0, 1.0)
    image_data = (normalized * 255.0).astype(np.uint8)
    if image_data.shape[-1] == 1:
        image_data = image_data[..., 0]
    image = Image.fromarray(image_data, mode=target_mode)

    if mkdirs:
        path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return {"path": str(path)}
