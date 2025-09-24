"""UI integration tests for the GraphController."""

from __future__ import annotations

import os

import pytest
from PySide6 import QtWidgets

from hesiod_py.ui.controller import GraphController


def _ensure_qapplication() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_graph_controller_evaluates_simple_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    _ensure_qapplication()

    controller = GraphController()
    controller.create_node("primitives.constant", position=(0, 0))
    controller.create_node("math.add", position=(320, 0))

    nodes_by_type = {
        getattr(node.__class__, "METADATA").type: node
        for node in controller.node_graph.all_nodes()
        if hasattr(node.__class__, "METADATA")
    }

    constant_node = nodes_by_type["primitives.constant"]
    add_node = nodes_by_type["math.add"]

    constant_node.set_property("value", 3.0)
    add_node.set_property("lhs", 0.0)
    add_node.set_property("rhs", 0.0)

    add_node.set_input(0, constant_node.output(0))
    add_node.set_input(1, constant_node.output(0))

    results = controller.evaluate([str(add_node.id)])
    add_outputs = results[str(add_node.id)]
    assert pytest.approx(add_outputs["output"], rel=1e-6) == 6.0
