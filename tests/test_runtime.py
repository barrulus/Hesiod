from __future__ import annotations

from collections.abc import Mapping

import pytest
from hesiod_py.core.graph import Graph, Node
from hesiod_py.core.registry import NodeRegistry
from hesiod_py.core.runtime import ExecutionCache, GraphScheduler, RuntimeContext
from hesiod_py.nodes.primitives import register_primitives


@pytest.fixture()
def graph() -> Graph:
    g = Graph(name="test")
    g.add_node(Node(key="c1", type="primitives.constant", parameters={"value": 2.0}))
    g.add_node(Node(key="c2", type="primitives.constant", parameters={"value": 3.0}))
    g.add_node(Node(key="add", type="math.add"))
    g.add_node(Node(key="mul", type="math.multiply", parameters={"rhs": 10.0}))
    g.connect(source_node="c1", source_port="output", target_node="add", target_port="lhs")
    g.connect(source_node="c2", source_port="output", target_node="add", target_port="rhs")
    g.connect(source_node="add", source_port="output", target_node="mul", target_port="lhs")
    return g


@pytest.fixture()
def scheduler(graph: Graph) -> GraphScheduler:
    local_registry = NodeRegistry()
    register_primitives(local_registry)
    return GraphScheduler(graph, node_registry=local_registry)


def test_scheduler_executes_graph(scheduler: GraphScheduler) -> None:
    results = scheduler.evaluate(targets=["mul"])
    assert results["mul"]["output"] == pytest.approx(50.0)


def test_scheduler_reuses_cache(graph: Graph) -> None:
    local_registry = NodeRegistry()
    register_primitives(local_registry)
    call_counter = {"count": 0}

    def counting_constant(
        node: Node,
        inputs: Mapping[str, object],
        context: RuntimeContext,
    ) -> dict[str, object]:
        call_counter["count"] += 1
        return {"output": node.parameters.get("value", 0)}

    local_registry.register("test.constant", counting_constant)
    graph.add_node(Node(key="count", type="test.constant", parameters={"value": 1}))
    graph.connect(source_node="count", source_port="output", target_node="mul", target_port="rhs")

    scheduler = GraphScheduler(graph, node_registry=local_registry)
    scheduler.evaluate(targets=["mul"])
    scheduler.evaluate(targets=["mul"])

    assert call_counter["count"] == 1

    graph.nodes["count"].update_parameters({"value": 5})
    graph.mark_dirty("count")
    scheduler.evaluate(targets=["mul"])
    assert call_counter["count"] == 2


def test_execution_cache_invalidates() -> None:
    cache = ExecutionCache()
    cache.store("node", "sig", {"output": 1})
    assert cache.is_valid("node", "sig")
    cache.invalidate("node")
    assert not cache.is_valid("node", "sig")
