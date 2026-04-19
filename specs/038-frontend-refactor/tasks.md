# Tasks: 038 Frontend UI Modular Refactor

This document contains the actionable, dependency-ordered tasks to complete the `038-frontend-refactor` specification.

## Phase 1: Setup

The setup phase initializes the file structure required for the new sub-components.

- [x] T001 Initialize empty LitElement files in `custom_components/house_battery_control/frontend/hbc-dashboard.js`, `frontend/hbc-sensors.js`, and `frontend/hbc-plan-table.js`.

## Phase 2: Foundational Component Extraction

> **User Story 1**: Decoupling visual components from the orchestrator logic into atomic Web Components strictly constrained to under 300 LOC.

- [x] T002 [US1] Migrate `_renderDashboard` SVG generation, flow-graph CSS, and HTML from `frontend/hbc-panel.js` into the `render()` method of `frontend/hbc-dashboard.js`, ensuring it registers as `<hbc-dashboard>`.
- [x] T003 [P] [US1] Migrate `_renderSensors` layout, error badge logic, and sensor CSS from `frontend/hbc-panel.js` into `frontend/hbc-sensors.js`, ensuring it registers as `<hbc-sensors>`.
- [x] T004 [US1] Migrate the comprehensive `_renderPlan` algorithm, mathematically chunking blocks, `_calculateSummaryStats`, and table CSS from `frontend/hbc-panel.js` into `frontend/hbc-plan-table.js`, ensuring it registers as `<hbc-plan-table>`.

## Phase 3: The Orchestrator Engine

> **User Story 2**: Pushing the data payload to sub-components cleanly without prop-drilling or monolithic render cycles.

- [x] T005 [US2] Update `frontend/hbc-panel.js` by unconditionally deleting all previously extracted internal rendering/styling methods (`_renderDashboard`, `_renderSensors`, `_renderPlan`, `_calculateSummaryStats`).
- [x] T006 [US2] Update `frontend/hbc-panel.js` to utilize ES6 module imports for the new components (`import './hbc-dashboard.js';` etc) and refactor the primary `render()` block to dynamically return the custom tags (`<hbc-dashboard .data=${this._data}></hbc-dashboard>`, etc) strictly driven by `this._activeTab`.

## Phase 4: Polish & Cross-Cutting Concerns

- [x] T007 Verify the dynamic tab-reload logic safely initializes all sub-components without browser layout thrashing on cold cache.
- [x] T008 Prove `localStorage` keys for the Plan Table hidden columns (`hbc_hidden_cols`) and Sensor states (`hbc_sensors_hidden`) successfully isolate to their respective child components.

---

## Dependencies

```text
T001 (Setup)
  |-- T002 (Dashboard) --> T005 (Orchestrator Strip)
  |-- T003 (Sensors)   --> T005
  |-- T004 (Plan Table)--> T005
                             |--> T006 (Orchestrator Import)
                                   |--> T007/T008 (Verification)
```

## Implementation Strategy

1. Work strictly from the highest independent visual leaf node to the lowest integration point (e.g., extract the passive Sensors and Dashboard components first, as they do not manipulate heavy state).
2. The `hbc-plan-table.js` is the most difficult extraction as it relies heavily on native UI properties. Ensure `localStorage` state tracking is migrated natively into this file.
3. The final cutover (`T005`/`T006`) should be atomic to avoid partial broken states in the UI.
