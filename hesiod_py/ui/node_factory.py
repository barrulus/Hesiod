"""Helpers for building NodeGraphQt node classes from Hesiod metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from ..core.registry import NodeMetadata, ParameterSpec, PortSpec
from ._compat import ensure_distutils

ensure_distutils()

from NodeGraphQt import BaseNode  # noqa: E402  # type: ignore
from NodeGraphQt.base.model import NodeModel  # noqa: E402  # type: ignore
from NodeGraphQt.constants import NodePropWidgetEnum  # noqa: E402  # type: ignore

__all__ = ["HesiodNode", "build_node_class", "categorise_metadata"]


# Basic colour palette for common Hesiod data types (RGB 0-255)
_DATA_TYPE_COLORS: Mapping[str, tuple[int, int, int]] = {
    "scalar": (200, 200, 200),
    "heightmap": (90, 150, 220),
    "mask": (200, 120, 70),
    "texture": (200, 90, 170),
    "path": (140, 140, 140),
    "dict": (170, 170, 110),
}

_RESERVED_PROPERTY_NAMES = set(NodeModel().properties.keys())


def _color_for_data_type(data_type: str) -> tuple[int, int, int]:
    return _DATA_TYPE_COLORS.get(data_type.lower(), (130, 130, 130))


def _sanitize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_.]", "_", value.lower())


def _class_name_from_type(value: str) -> str:
    parts = re.split(r"[._]+", value)
    return "".join(part.capitalize() for part in parts if part) + "Node"


def _widget_for_parameter(node_type: str, spec: ParameterSpec) -> NodePropWidgetEnum:
    param_type = spec.param_type.lower()
    if param_type == "bool":
        return NodePropWidgetEnum.QCHECK_BOX
    if param_type == "enum":
        return NodePropWidgetEnum.QCOMBO_BOX
    if param_type == "path":
        if node_type.startswith("export."):
            return NodePropWidgetEnum.FILE_SAVE
        return NodePropWidgetEnum.FILE_OPEN
    if param_type == "float":
        if spec.default is None:
            return NodePropWidgetEnum.QLINE_EDIT
        return NodePropWidgetEnum.FLOAT
    if param_type == "int":
        if spec.default is None:
            return NodePropWidgetEnum.QLINE_EDIT
        return NodePropWidgetEnum.INT
    return NodePropWidgetEnum.QLINE_EDIT


def _initial_value(spec: ParameterSpec, widget: NodePropWidgetEnum) -> object:
    value = spec.default
    if widget == NodePropWidgetEnum.QCHECK_BOX:
        return bool(value)
    if widget == NodePropWidgetEnum.QCOMBO_BOX:
        choices = list(spec.choices or ())
        if not choices:
            return ""
        if value in choices:
            return value
        return choices[0]
    if widget in {NodePropWidgetEnum.FILE_OPEN, NodePropWidgetEnum.FILE_SAVE}:
        return str(value) if value else ""
    if widget == NodePropWidgetEnum.FLOAT:
        return float(value) if value is not None else 0.0
    if widget == NodePropWidgetEnum.INT:
        return int(value) if value is not None else 0
    if widget == NodePropWidgetEnum.QLINE_EDIT:
        return "" if value is None else str(value)
    return value


def _safe_property_name(name: str, taken: set[str]) -> str:
    candidate = name
    if candidate in taken:
        candidate = f"param_{candidate}"
    suffix = 1
    while candidate in taken:
        candidate = f"{candidate}_{suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate


@dataclass(slots=True)
class _ParameterConfig:
    widget: NodePropWidgetEnum
    default: object
    choices: Sequence[object] | None
    tooltip: str | None


class HesiodNode(BaseNode):
    """Base class used for dynamically generated Hesiod nodes."""

    METADATA: NodeMetadata
    PARAMETER_CONFIG: dict[str, _ParameterConfig]
    PARAMETER_PROPERTY_NAMES: dict[str, str]
    PROPERTY_TO_PARAMETER: dict[str, str]

    def __init__(self) -> None:
        super().__init__()
        metadata = self.METADATA
        self._parameter_names = tuple(spec.name for spec in metadata.parameters)
        self._property_names = self.PARAMETER_PROPERTY_NAMES
        self.view.setToolTip(metadata.description or metadata.label)
        self._build_ports(metadata.inputs, is_output=False)
        self._build_ports(metadata.outputs, is_output=True)
        self._build_parameters()

    def _build_ports(self, ports: Sequence[PortSpec], *, is_output: bool) -> None:
        for port_spec in ports:
            color = _color_for_data_type(port_spec.data_type)
            if is_output:
                port = self.add_output(port_spec.name, color=color)
            else:
                port = self.add_input(port_spec.name, color=color)
            if port_spec.description:
                port.view.setToolTip(port_spec.description)

    def _build_parameters(self) -> None:
        for name, config in self.PARAMETER_CONFIG.items():
            property_name = self._property_names[name]
            items = list(config.choices) if config.choices else None
            self.create_property(
                property_name,
                config.default,
                items=items,
                widget_type=config.widget.value,
                widget_tooltip=config.tooltip,
            )

    @property
    def parameter_names(self) -> tuple[str, ...]:
        return self._parameter_names


def _parameter_config(node_type: str, spec: ParameterSpec) -> _ParameterConfig:
    widget = _widget_for_parameter(node_type, spec)
    default = _initial_value(spec, widget)
    tooltip = spec.description or None
    choices = spec.choices if spec.choices else None
    return _ParameterConfig(widget=widget, default=default, choices=choices, tooltip=tooltip)


def build_node_class(metadata: NodeMetadata) -> type[HesiodNode]:
    """Create a NodeGraphQt node class from Hesiod metadata."""
    class_name = _class_name_from_type(metadata.type)
    identifier = f"hesiod.{_sanitize_identifier(metadata.category or 'general')}"
    parameter_config = {
        spec.name: _parameter_config(metadata.type, spec)
        for spec in metadata.parameters
    }
    taken_names = set(_RESERVED_PROPERTY_NAMES)
    param_to_property: dict[str, str] = {}
    for spec in metadata.parameters:
        param_to_property[spec.name] = _safe_property_name(spec.name, taken_names)

    attributes = {
        "__identifier__": identifier,
        "NODE_NAME": metadata.label,
        "METADATA": metadata,
        "PARAMETER_CONFIG": parameter_config,
        "PARAMETER_PROPERTY_NAMES": param_to_property,
        "PROPERTY_TO_PARAMETER": {prop: param for param, prop in param_to_property.items()},
    }
    return type(class_name, (HesiodNode,), attributes)


def categorise_metadata(metadata: Iterable[NodeMetadata]) -> dict[str, list[NodeMetadata]]:
    """Group metadata entries by category for palette display."""
    categories: dict[str, list[NodeMetadata]] = {}
    for entry in metadata:
        key = entry.category or "Other"
        categories.setdefault(key, []).append(entry)
    for values in categories.values():
        values.sort(key=lambda item: item.label)
    return dict(sorted(categories.items(), key=lambda item: item[0].lower()))
