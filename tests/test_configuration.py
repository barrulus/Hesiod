from __future__ import annotations

from pathlib import Path

import pytest
from hesiod_py.core.configuration import (
    AppConfiguration,
    ConfigurationError,
    RuntimePaths,
    RuntimePerformance,
    load_configuration,
    save_configuration,
)


def build_config(tmp_path: Path) -> AppConfiguration:
    return AppConfiguration(
        paths=RuntimePaths(
            project_root=tmp_path,
            cache_dir=tmp_path / "cache",
            asset_dir=tmp_path / "assets",
        ),
        performance=RuntimePerformance(enable_multiprocessing=False, worker_concurrency=2),
        metadata={"version": "test"},
    )


def test_configuration_roundtrip(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    target = tmp_path / "config.json"
    save_configuration(config, target)
    loaded = load_configuration(target)
    assert loaded.paths.project_root == config.paths.project_root
    assert loaded.performance.worker_concurrency == 2
    assert loaded.metadata["version"] == "test"


def test_configuration_invalid_json(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text("not json", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_configuration(target)


def test_configuration_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_configuration(tmp_path / "missing.json")
