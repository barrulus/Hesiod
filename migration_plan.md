# Hesiod Python Migration Plan

## Overview
- Objective: transition Hesiod from its current C++/Qt6 implementation to a modular Python application with a lighter dependency footprint, extensible node graph engine, and built-in mosaic tooling.
- Guiding principles: maintain critical user workflows, favour pure-Python or widely supported libraries, keep the project buildable via standard Python packaging, and document each step to ease onboarding.
- Workstreams: discovery, architecture, runtime porting, node migration, UI rebuild, mosaic tooling, QA and documentation.

## Phase 0 - Discovery and Requirements Alignment
Goal: capture the current feature surface, decide MVP scope, and define quality and performance targets for the Python rewrite.

Sequential tasks:
1. Inventory active user workflows, required node categories, and existing automation scripts by interviewing stakeholders and reviewing sample .hsd projects.
2. Audit third-party dependencies (Qt, OpenCL, HighMap, GNode, and others) to decide which behaviours must be re-implemented, replaced, or can be deferred.
3. Classify nodes into must-have, nice-to-have, and deprecated buckets; record rationale for every exclusion.
4. Document performance, resource, and platform expectations such as target resolution, GPU or CPU requirements, and Windows or Linux parity.
5. Produce a baseline risk register covering data fidelity, UI parity, and algorithmic gaps.
6. Secure stakeholder sign-off on MVP scope, success criteria, and phased delivery timeline.

Exit criteria:
- Approved scope document with prioritised node list and functional requirements.
- Agreed performance targets and supported platforms.
- Risks logged with initial mitigation owners.

## Phase 1 - Architecture and Infrastructure Setup
Goal: establish the Python repository structure, tooling, and design foundations needed for iterative development.

Sequential tasks:
1. Scaffold the Python package (for example, hesiod_py/) with subpackages for core, nodes, io, ui, plugins, and data.
2. Adopt a build system (Poetry, uv, or Hatch) and define dependency constraints, linting (ruff or flake8), formatting (black), and type checking (mypy or pyright).
3. Configure continuous integration to run linting, unit tests, and package builds on Windows and Linux.
4. Specify configuration and serialization formats (JSON or YAML) and create shared utility modules for logging, configuration loading, and asset management.
5. Draft high-level architecture diagrams covering runtime, UI, and mosaic builder components; review them with the team.
6. Implement contributor documentation such as contributing guidelines, coding standards, and repository bootstrapping instructions.

Exit criteria:
- Python repository builds and passes lint or test in continuous integration.
- Architecture documents approved and stored in the docs folder.
- Developer onboarding guide published.

## Phase 2 - Core Runtime Port
Goal: replace the C++ graph execution engine with a Python runtime that can evaluate node graphs, manage state, and interoperate with legacy data.

Sequential tasks:
1. Implement graph model classes (project, graph, node, port) using dataclasses and directed acyclic scheduling.
2. Build dependency resolution and execution scheduler with incremental recompute support and memoisation hooks.
3. Define heightmap or mesh data abstractions using numpy arrays, including metadata for bounds, tiling, and resolution.
4. Port configuration management (model config, export parameters, broadcasting) and ensure JSON round-trip fidelity.
5. Create a legacy .hsd importer that maps C++ node definitions to Python equivalents, logging unsupported nodes.
6. Establish automated tests covering graph creation, serialization, and basic node execution pipelines.

Exit criteria:
- Python runtime loads and executes sample graphs with foundational nodes.
- Legacy .hsd projects can be ingested with clear reporting on gaps.
- Test suite validates scheduler correctness and data structure integrity.

## Phase 3 - Node Library Migration
Goal: deliver a functional set of Python node implementations that cover the agreed MVP scope while reducing reliance on external C++ libraries.

Sequential tasks:
1. Implement core primitive nodes (noise, constants, transforms) using numpy, numba, or scipy as needed; verify outputs against C++ baselines.
2. Port blend, filter, and masking nodes, ensuring consistent parameter handling and attribute validation.
3. Recreate export and import nodes (heightmap, texture, normal map) with Pillow or imageio wrappers and optional GDAL hooks when justified.
4. Migrate erosion, geological, and quilting algorithms; document any approximations or performance deviations.
5. Build a registry or metadata system so nodes self-describe inputs, outputs, UI editors, and documentation.
6. Author unit and property tests, plus image-diff regression suites for deterministic nodes; capture benchmarks where performance is critical.

Exit criteria:
- MVP node set implemented and registered with automated verification.
- Documentation generated from node metadata and published in the docs folder.
- Performance benchmarks meeting or exceeding agreed thresholds.

## Phase 4 - Python UI and Experience
Goal: deliver a PySide6 or PyQt based desktop interface that replicates essential Hesiod workflows and integrates with the Python runtime.

Sequential tasks:
1. Evaluate node-editor libraries (NodeGraphQt, Ryven, or custom) and choose an approach balancing features, maintenance, and licensing.
2. Implement graph canvas, node palette, property inspector, and viewport preview panes with theme support.
3. Integrate runtime execution, including progress feedback, error handling, and live previews for selected nodes.
4. Recreate project management features (graph tabs, autosave, import or export dialogs) and connect them to the Python runtime API.
5. Implement logging, notifications, and diagnostics panels to replace existing toast or log functionality.
6. Conduct usability testing sessions with power users, collecting feedback for iterative UI refinements.

Exit criteria:
- GUI supports building, editing, executing, and exporting graphs end to end.
- Usability feedback incorporated into a tracked backlog.
- Packaging scripts (PyInstaller or Briefcase) validated for Windows and Linux.

## Phase 5 - Mosaic Builder and Release Preparation
Goal: add advanced composition tooling, harden the platform, and prepare for public release.

Sequential tasks:
1. Implement mosaic builder services for tile stitching, reprojection, and atlas export, integrating with runtime and UI.
2. Provide CLI commands for batch processing, mosaic generation, and automation comparable to the current C++ tooling.
3. Finalise documentation: user guide, developer API references, migration notes for legacy users, and tutorials.
4. Expand automated testing to include integration suites, stress tests with large datasets, and cross-platform installers.
5. Conduct performance tuning, profiling hot paths, and applying optimisations or GPU acceleration where necessary.
6. Execute release checklist: versioning, changelog, license review, launch communications, and long-term maintenance plan.

Exit criteria:
- Mosaic builder validated through scripted tests and user scenarios.
- Documentation set complete and published (docs site or local HTML or PDF).
- Release candidate builds signed off, with maintenance roadmap agreed.

## Cross-Phase Governance
- Maintain a living roadmap and burndown, updating phase deliverables as user feedback arrives.
- Review risks, assumptions, and mitigation actions at each phase gate.
- Track technical debt, ensuring deferred items receive backlog entries with owners and due windows.

