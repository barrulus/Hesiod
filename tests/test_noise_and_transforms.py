from __future__ import annotations

import numpy as np
import pytest
from hesiod_py.core.graph import Graph, Node
from hesiod_py.core.registry import NodeRegistry
from hesiod_py.core.runtime import GraphScheduler
from hesiod_py.nodes.noise import register_noise_nodes
from hesiod_py.nodes.transforms import register_transform_nodes


@pytest.fixture()
def registry() -> NodeRegistry:
    reg = NodeRegistry()
    register_noise_nodes(reg)
    register_transform_nodes(reg)
    return reg


def test_uniform_noise_is_deterministic(registry: NodeRegistry) -> None:
    graph = Graph(name="noise-test")
    graph.add_node(
        Node(
            key="uniform",
            type="noise.uniform",
            parameters={"width": 4, "height": 3, "low": -1.0, "high": 1.0, "seed": 42},
        )
    )
    scheduler = GraphScheduler(graph, node_registry=registry)
    results = scheduler.evaluate(targets=["uniform"])
    heightmap = results["uniform"]["heightmap"]
    assert heightmap.resolution == (3, 4)
    expected = np.array(
        [
            [0.5479121, -0.12224312, 0.71719587, 0.39473605],
            [-0.8116453, 0.9512447, 0.5222794, 0.5721286],
            [-0.74377275, -0.09922812, -0.25840396, 0.85352999],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(heightmap.data, expected, rtol=1e-6, atol=1e-6)


def test_scale_bias_transform(registry: NodeRegistry) -> None:
    graph = Graph(name="transform-test")
    graph.add_node(
        Node(
            key="uniform",
            type="noise.uniform",
            parameters={"width": 2, "height": 2, "low": 0.0, "high": 1.0, "seed": 7},
        )
    )
    graph.add_node(
        Node(
            key="scaled",
            type="transform.scale_bias",
            parameters={"scale": 2.0, "bias": -0.5},
        )
    )
    graph.connect(
        source_node="uniform",
        source_port="heightmap",
        target_node="scaled",
        target_port="source",
    )

    scheduler = GraphScheduler(graph, node_registry=registry)
    results = scheduler.evaluate(targets=["scaled"])
    heightmap = results["scaled"]["heightmap"]
    base = np.array(
        [[0.6250955, 0.8972138], [0.77568567, 0.22520719]],
        dtype=np.float32,
    )
    expected = (base * 2.0) - 0.5
    np.testing.assert_allclose(heightmap.data, expected.astype(np.float32), atol=1e-6)


def test_normalize_handles_constant_surface(registry: NodeRegistry) -> None:
    graph = Graph(name="normalize-test")
    graph.add_node(
        Node(
            key="uniform",
            type="noise.uniform",
            parameters={"width": 2, "height": 2, "low": 0.5, "high": 0.5, "seed": 1},
        )
    )
    graph.add_node(
        Node(
            key="normalized",
            type="transform.normalize",
            parameters={"min": -1.0, "max": 1.0},
        )
    )
    graph.connect(
        source_node="uniform",
        source_port="heightmap",
        target_node="normalized",
        target_port="source",
    )

    scheduler = GraphScheduler(graph, node_registry=registry)
    results = scheduler.evaluate(targets=["normalized"])
    heightmap = results["normalized"]["heightmap"]
    np.testing.assert_allclose(heightmap.data, np.full((2, 2), -1.0, dtype=np.float32))
