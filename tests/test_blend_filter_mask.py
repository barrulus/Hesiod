from __future__ import annotations

import numpy as np
import pytest
from hesiod_py.core.graph import Node
from hesiod_py.core.registry import NodeRegistry
from hesiod_py.data.structures import HeightMap
from hesiod_py.nodes.blend import register_blend_nodes
from hesiod_py.nodes.filter import register_filter_nodes
from hesiod_py.nodes.mask import register_mask_nodes
from hesiod_py.nodes.noise import register_noise_nodes
from hesiod_py.nodes.primitives import register_primitives
from hesiod_py.nodes.transforms import register_transform_nodes


class _DummyContext:
    def __init__(self) -> None:
        self.state: dict[str, object] = {}


@pytest.fixture()
def registry() -> NodeRegistry:
    reg = NodeRegistry()
    register_primitives(reg)
    register_noise_nodes(reg)
    register_transform_nodes(reg)
    register_blend_nodes(reg)
    register_filter_nodes(reg)
    register_mask_nodes(reg)
    return reg


@pytest.fixture()
def context() -> _DummyContext:
    return _DummyContext()


def test_linear_blend_handler(registry: NodeRegistry, context: _DummyContext) -> None:
    handler = registry.get("blend.linear").handler
    node = Node(key="blend", type="blend.linear", parameters={"factor": 0.25})
    fg = HeightMap(data=np.ones((2, 2), dtype=np.float32), bounds=(0, 2, 0, 2))
    bg = HeightMap(data=np.zeros((2, 2), dtype=np.float32), bounds=(0, 2, 0, 2))
    outputs = handler(node, {"foreground": fg, "background": bg}, context)
    blended = outputs["heightmap"].data
    np.testing.assert_allclose(blended, np.full((2, 2), 0.25, dtype=np.float32))


def test_additive_blend(registry: NodeRegistry, context: _DummyContext) -> None:
    handler = registry.get("blend.add").handler
    node = Node(key="add", type="blend.add", parameters={"scale": 0.5, "bias": -1.0})
    a = HeightMap(data=np.full((2, 2), 2.0, dtype=np.float32), bounds=(0, 2, 0, 2))
    b = HeightMap(data=np.full((2, 2), 4.0, dtype=np.float32), bounds=(0, 2, 0, 2))
    outputs = handler(node, {"source_a": a, "source_b": b}, context)
    expected = ((a.data + b.data) * 0.5) - 1.0
    np.testing.assert_allclose(outputs["heightmap"].data, expected)


def test_box_blur_preserves_mean(registry: NodeRegistry, context: _DummyContext) -> None:
    handler = registry.get("filter.box_blur").handler
    node = Node(key="box", type="filter.box_blur", parameters={"kernel_size": 3})
    data = np.arange(16, dtype=np.float32).reshape(4, 4)
    hm = HeightMap(data=data, bounds=(0, 4, 0, 4))
    outputs = handler(node, {"source": hm}, context)
    blurred = outputs["heightmap"].data
    np.testing.assert_allclose(blurred.mean(), data.mean(), atol=1e-6)
    assert blurred.shape == data.shape


def test_gaussian_blur_softens_impulse(registry: NodeRegistry, context: _DummyContext) -> None:
    handler = registry.get("filter.gaussian_blur").handler
    node = Node(
        key="gaussian",
        type="filter.gaussian_blur",
        parameters={"kernel_size": 5, "sigma": 1.0},
    )
    data = np.zeros((7, 7), dtype=np.float32)
    data[3, 3] = 1.0
    hm = HeightMap(data=data, bounds=(0, 7, 0, 7))
    outputs = handler(node, {"source": hm}, context)
    blurred = outputs["heightmap"].data
    assert blurred[3, 3] < 1.0
    np.testing.assert_allclose(blurred.sum(), hm.data.sum(), atol=1e-6)


def test_mask_threshold_and_apply(registry: NodeRegistry, context: _DummyContext) -> None:
    threshold_handler = registry.get("mask.threshold").handler
    apply_handler = registry.get("mask.apply").handler
    invert_handler = registry.get("mask.invert").handler

    node_threshold = Node(
        key="threshold",
        type="mask.threshold",
        parameters={"threshold": 0.5, "mode": "greater_equal"},
    )
    node_apply = Node(key="apply", type="mask.apply", parameters={"fill": -1.0})
    node_invert = Node(key="invert", type="mask.invert", parameters={})

    data = np.array([[0.2, 0.6], [0.8, 0.4]], dtype=np.float32)
    hm = HeightMap(data=data, bounds=(0, 2, 0, 2))

    mask_output = threshold_handler(node_threshold, {"source": hm}, context)
    mask = mask_output["mask"]

    inverted = invert_handler(node_invert, {"mask": mask}, context)
    applied = apply_handler(node_apply, {"source": hm, "mask": mask}, context)

    expected_mask = (data >= 0.5).astype(np.float32)
    np.testing.assert_allclose(mask.data, expected_mask)
    np.testing.assert_allclose(inverted["mask"].data, 1.0 - expected_mask)
    np.testing.assert_allclose(
        applied["heightmap"].data,
        data * expected_mask + (-1.0) * (1.0 - expected_mask),
    )
