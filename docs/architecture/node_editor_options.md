# Node Editor Options for Phase 4

## Evaluation Goals
- Integrate with PySide6 to stay within Qt ecosystem and match Hesiod�s desktop UX.
- Provide node-graph editing primitives (nodes, sockets, connections, zoom/pan canvas).
- Allow custom styling and widgets for property inspectors.
- Remain maintainable with permissive licensing and healthy community.

## Candidates

### NodeGraphQt
- **Summary**: PySide/PyQt based node editor library built on QGraphicsScene.
- **License**: MIT.
- **Pros**:
  - Native PySide6 support and tested on Qt6.
  - Mature API for node/port definitions, actions, context menus, serialization hooks.
  - Active maintenance and documentation; integrates cleanly with custom widgets.
- **Cons**:
  - Adds dependency (~1.3k LOC) and implicit reliance on QGraphicsScene paradigms.
  - Styling requires Qt stylesheet work to match Hesiod branding.

### Ryven
- **Summary**: Full visual scripting environment built on PySide.
- **License**: GPL-3.0.
- **Pros**: Feature-rich with scripting, param widgets, preview nodes.
- **Cons**: GPL-3 incompatible with Hesiod licensing; heavy-weight (bundled app) rather than embeddable widget; limited Qt6 maturity.

### Custom PySide6 Scene
- **Summary**: Build QGraphicsScene/QGraphicsView implementation from scratch.
- **Pros**: Full control over UX, performance, and data model alignment.
- **Cons**: Significant effort to reach feature parity (selection behavior, edge routing, undo/redo); high maintenance cost.

## Recommendation
Proceed with **NodeGraphQt**:
- Meets licensing requirements (MIT) and PySide6 compatibility.
- Provides a modular canvas we can host inside our PySide6 main window while retaining control over node palettes, inspectors, and runtime integration.
- Allows incremental customization: we can start with the core widget, then override node styles and dock widgets to match Hesiod.

Next steps:
1. Add NodeGraphQt as a dependency alongside PySide6.
2. Prototype a shell application embedding NodeGraphQt with custom node registry binding.
3. Document theming/extension points for later UX work.

## Status (2025-09-23)
- NodeGraphQt prototype implemented in the PySide6 shell with runtime bridge and preview pane; see MIGRATION_ACTION.md for integration details.
