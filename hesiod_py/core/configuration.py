"""Configuration management utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

__all__ = ["AppConfiguration", "ConfigurationError", "load_configuration", "save_configuration"]


class ConfigurationError(RuntimeError):
    """Raised when configuration files cannot be parsed."""


class RuntimePaths(BaseModel):
    project_root: Path
    cache_dir: Path
    asset_dir: Path


class RuntimePerformance(BaseModel):
    enable_multiprocessing: bool = Field(default=True)
    enable_memoization: bool = Field(default=True)
    worker_concurrency: int = Field(default=0, ge=0, le=64)


class AppConfiguration(BaseModel):
    """Top level configuration document."""

    paths: RuntimePaths
    performance: RuntimePerformance = Field(default_factory=RuntimePerformance)
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
    }


def load_configuration(path: Path) -> AppConfiguration:
    """Load configuration from a JSON file."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON configuration: {path}") from exc

    try:
        return AppConfiguration.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(str(exc)) from exc


def save_configuration(config: AppConfiguration, path: Path) -> None:
    """Persist configuration to disk."""

    payload = json.loads(config.model_dump_json(indent=2))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
