"""Primitive nodes implemented in Python."""

from __future__ import annotations

from collections.abc import Mapping

from ..core.graph import Node
from ..core.registry import (
    ExecutionContext,
    NodeMetadata,
    NodeRegistry,
    ParameterSpec,
    PortSpec,
    registry,
)

__all__ = ["register_primitives"]


def _coerce_scalar(value: object, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


_PRIMITIVE_NODES = {
    "primitives.constant": NodeMetadata(
        type="primitives.constant",
        label="Constant",
        category="Primitive",
        inputs=(),
        outputs=(
            PortSpec(
                name="output",
                data_type="scalar",
                description="Constant value",
            ),
        ),
        parameters=(
            ParameterSpec(
                name="value",
                param_type="float",
                default=0.0,
                description="Value emitted by the node.",
            ),
        ),
        description="Emit a scalar constant value.",
        tags=("primitive", "math"),
    ),
    "math.add": NodeMetadata(
        type="math.add",
        label="Add",
        category="Math",
        inputs=(
            PortSpec(name="lhs", data_type="scalar", description="Left-hand value"),
            PortSpec(name="rhs", data_type="scalar", description="Right-hand value"),
        ),
        outputs=(PortSpec(name="output", data_type="scalar", description="Sum of inputs"),),
        parameters=(
            ParameterSpec(
                name="lhs",
                param_type="float",
                default=0.0,
                description="Default left value",
            ),
            ParameterSpec(
                name="rhs",
                param_type="float",
                default=0.0,
                description="Default right value",
            ),
        ),
        description="Add two scalar values.",
        tags=("primitive", "math"),
    ),
    "math.multiply": NodeMetadata(
        type="math.multiply",
        label="Multiply",
        category="Math",
        inputs=(
            PortSpec(name="lhs", data_type="scalar", description="Left-hand value"),
            PortSpec(name="rhs", data_type="scalar", description="Right-hand value"),
        ),
        outputs=(PortSpec(name="output", data_type="scalar", description="Product of inputs"),),
        parameters=(
            ParameterSpec(
                name="lhs",
                param_type="float",
                default=1.0,
                description="Default left value",
            ),
            ParameterSpec(
                name="rhs",
                param_type="float",
                default=1.0,
                description="Default right value",
            ),
        ),
        description="Multiply two scalar values.",
        tags=("primitive", "math"),
    ),
}


def register_primitives(node_registry: NodeRegistry | None = None) -> None:
    target = node_registry or registry
    target.register(
        "primitives.constant",
        _constant_node,
        description="Emit a scalar constant",
        metadata=_PRIMITIVE_NODES["primitives.constant"],
    )
    target.register(
        "math.add",
        _add_node,
        description="Add two scalar inputs",
        metadata=_PRIMITIVE_NODES["math.add"],
    )
    target.register(
        "math.multiply",
        _multiply_node,
        description="Multiply two scalar inputs",
        metadata=_PRIMITIVE_NODES["math.multiply"],
    )


def _constant_node(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    value = _coerce_scalar(node.parameters.get("value", 0.0), 0.0)
    return {"output": value}


def _add_node(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    lhs_default = _coerce_scalar(node.parameters.get("lhs", 0.0), 0.0)
    rhs_default = _coerce_scalar(node.parameters.get("rhs", 0.0), 0.0)
    lhs = _coerce_scalar(inputs.get("lhs", lhs_default), lhs_default)
    rhs = _coerce_scalar(inputs.get("rhs", rhs_default), rhs_default)
    return {"output": lhs + rhs}


def _multiply_node(
    node: Node,
    inputs: Mapping[str, object],
    context: ExecutionContext,
) -> Mapping[str, object]:
    lhs_default = _coerce_scalar(node.parameters.get("lhs", 1.0), 1.0)
    rhs_default = _coerce_scalar(node.parameters.get("rhs", 1.0), 1.0)
    lhs = _coerce_scalar(inputs.get("lhs", lhs_default), lhs_default)
    rhs = _coerce_scalar(inputs.get("rhs", rhs_default), rhs_default)
    return {"output": lhs * rhs}
