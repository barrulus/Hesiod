# Python Contributor Guide

## Environment Setup
- Install Python 3.11 or newer.
- Install Poetry 1.8+ and run `poetry install` from the repository root.
- Activate the virtual environment with `poetry shell` or prefix commands with `poetry run`.
- Install `pre-commit` hooks by running `poetry run pre-commit install` (hook configuration will be added in a later milestone).

## Code Quality
- Format code with `poetry run black .`.
- Lint with `poetry run ruff check .`.
- Type-check with `poetry run mypy .`.
- Execute the test suite with `poetry run pytest`.

## Repository Structure
- `hesiod_py/core` holds runtime primitives, graph types, configuration, and schedulers.
- `hesiod_py/nodes` contains Python implementations of graph nodes.
- `hesiod_py/io` hosts importers/exporters, including the `.hsd` bridge.
- `hesiod_py/ui` is reserved for the PySide-based editor built in Phase 4.

## Development Workflow
1. Create a feature branch named `feature/<summary>`.
2. Run formatting, linting, type-checking, and tests locally before pushing.
3. Update or add tests whenever logic changes.
4. Document behaviour and configuration updates under `docs/`.

## Continuous Integration
- GitHub Actions execute linting, tests, and packaging on Windows and Linux.
- Pipelines must remain green before merging to the main branch.

## Support
- File questions in the `#hesiod-python` Slack channel.
- Record risks, follow-ups, and deferred work in `MIGRATION_ACTION.md`.
