# MIGRATION ACTION LOG

## Snapshot (2025-09-20)
- **Objective**: Track progress and follow-ups for the C++ ? Python migration.
- **Owner**: Hesiod Python Working Group
- **Last Updated**: 2025-09-23

## Phase Summary
| Phase | Scope Highlights | Status | Notes |
| --- | --- | --- | --- |
| Phase 0 ? Discovery | Workflow inventory, dependency audit, MVP sign-off | ? Complete | Scope recommendations captured in migration_plan.md.
| Phase 1 ? Architecture & Infra | Python package scaffold, tooling, CI, contributor docs | ? Complete | `hesiod_py/`, `pyproject.toml`, CI workflow delivered; docs added under `docs/`.
| Phase 2 ? Core Runtime | Graph model, scheduler, data structures, legacy importer, unit tests | ? Complete | Runtime executes primitive nodes; importer reports unsupported nodes; tests cover scheduler & config.
| Phase 3 ? Node Library | MVP node parity, registry metadata, regression suites | ?? In Planning | Need to prioritise node categories and baselines; benchmarking harness unstarted.
| Phase 4 - Python UI | PySide-based editor, runtime integration, packaging | In Progress | NodeGraphQt shell prototype in PySide6 with runtime bridge and live preview for runtime outputs, themed UI shell, and execution progress feedback. |
| Phase 5 ? Mosaic & Release | Mosaic tooling, CLI, docs, release checklist | ? Not Started | Will depend on Phase 3/4 outputs.

## Burndown / Action Items
- [x] Scaffold Python runtime package and commit tooling (Phase 1).
- [x] Implement graph core, scheduler, importer, and smoke tests (Phase 2).
- [ ] Finalise MVP node parity list and baseline data sources (Phase 3).
- [x] Implement core primitive nodes (constants, noise, transforms) and unit tests (Phase 3).
- [x] Implement blend, filter, and mask nodes using numpy-based pipelines with tests (Phase 3).
- [x] Implement image import/export nodes for heightmaps, textures, and normal maps with Pillow wrappers (Phase 3).
- [x] Introduce node metadata registry for UI/Docs integration (Phase 3).
- [ ] Define benchmarking approach (CPU vs GPU) for critical nodes (Phase 3).
- [x] Select UI framework (PySide6 vs PyQt) and storyboard UX flows (Phase 4).
- [x] Build PySide6 NodeGraphQt shell with runtime bridge and headless smoke test (Phase 4).
- [x] Apply dark theme and panel styling to the NodeGraphQt shell (Phase 4).
- [x] Surface execution progress and disable run controls during evaluation (Phase 4).
- [ ] Draft CLI and automation requirements for mosaic builder (Phase 5).
- [ ] Establish release governance (versioning policy, maintenance roadmap) (Phase 5).

## Risks & Mitigations
- **Node Parity Uncertainty** (High): Need stakeholder confirmation on MVP node set.
  - _Mitigation_: Schedule review workshop; capture outputs in migration_plan.md & this log.
- **Performance Targets Undefined** (Medium): Python prototypes must meet existing runtime expectations.
  - _Mitigation_: Add benchmarking tasks to Phase 3 backlog; investigate numpy/numba/GPU options.
- **UI Framework Decision Lag** (Medium): Delays Phase 4 start.
  - _Mitigation_: Run spike comparing NodeGraphQt vs custom PySide implementation during Phase 3.

## Upcoming Checkpoints
- **2025-09-24**: Present Phase 3 node parity proposal for approval.
- **2025-10-01**: Review performance benchmarking strategy.
- **2025-10-08**: UX alignment session for Python UI.

## Notes
- Keep this document updated after each stakeholder review or scope change.
- Capture deferred technical debt items with owner & target in this log and issue tracker.

