# Specification: Frontend UI Modular Refactor

## Description

The Home Assistant web dashboard frontend (`hbc-panel.js`) has grown into a monolithic file approaching 1,000 lines. This technical debt restricts the safe inclusion of upcoming complex data visualizations (e.g. the 48-hour horizon analog search display). This feature entails refactoring the UI into natively scoped LitElement Web Components to ensure code modularity, keeping all newly extracted files beneath a ~300 Line Of Code (LOC) ceiling.

## Goals

- Eliminate monolithic UI code dependency.
- Extract complex chunking and table rendering algorithms into localized scope.
- Provide a clean component mounting target for future "Outlook" or "Diagnostics" tabs without risking the core dashboard function.

## User Scenarios

**Scenario 1: Web Dashboard Execution**
When a user launches the House Battery Control panel from the Home Assistant sidebar, the root routing component seamlessly delegates rendering to the new sub-components. The user perceives absolutely no difference in interface structure, CSS styling, caching feedback, or animation states.

**Scenario 2: Data Refresh Pipeline**
When the Python `RatesManager` pushes an updated pricing plan, the root `hbc-panel` catches the data fetch and trickles the JSON object down to the `<hbc-dashboard>`, `<hbc-plan-table>`, and `<hbc-sensors>` components via native property bindings, avoiding prop-drilling or global state mutations.

## Functional Requirements

- **FR-001**: The overarching UI logic must be decoupled into atomic LitElement Web Components.
- **FR-002**: All newly created components must adhere strictly to the prefix naming convention `hbc-` (e.g. `<hbc-dashboard>`, `<hbc-plan-table>`).
- **FR-003**: No single component file (JS/TS) shall exceed an approximate hard limit of 300 Lines of Code to ensure maintainable feature scaling.
- **FR-004**: The Python API backend (`web.py`) must require zero structural changes to accommodate this frontend refactor. All updates must be completely contained within the `frontend/` directory context.

## Success Criteria

1. The `hbc-panel.js` master file is reduced from ~900 lines to a lightweight router acting solely as the Home Assistant interface adapter.
2. The total footprint of the `custom_components/house_battery_control/frontend/` app consists of at least 4 distinct `.js` files.
3. Not a single web component file exceeds 350 lines of code (inclusive of integrated CSS).
4. All existing UI automation rendering, including the SVG power flows and the 5-min to 30-min data boundary chunking tables, remain fully operational visually.

## Assumptions

- LitElement natively supports ES-module local imports without requiring a generalized build pipeline (e.g. Webpack/Vite) within Home Assistant custom panel architecture.

## Out of Scope

- No new features, graphs, tabs, or logic are being added. This is strictly a 1:1 refactor of existing frontend code to clear the runway for Feature 037.
