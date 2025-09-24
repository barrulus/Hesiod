"""Bootstrap helpers for the Hesiod Python runtime."""

from __future__ import annotations

from pathlib import Path

from .core.configuration import AppConfiguration
from .core.logging import configure_logging
from .nodes.blend import register_blend_nodes
from .nodes.filter import register_filter_nodes
from .nodes.image_io import register_image_io_nodes
from .nodes.mask import register_mask_nodes
from .nodes.noise import register_noise_nodes
from .nodes.primitives import register_primitives
from .nodes.transforms import register_transform_nodes

__all__ = ["bootstrap"]


def bootstrap(
    *,
    log_dir: Path | None = None,
    configuration: AppConfiguration | None = None,
) -> None:
    configure_logging(log_dir=log_dir)
    register_primitives()
    register_noise_nodes()
    register_transform_nodes()
    register_blend_nodes()
    register_filter_nodes()
    register_mask_nodes()
    register_image_io_nodes()

    if configuration is None:
        return
    configuration.paths.cache_dir.mkdir(parents=True, exist_ok=True)
