# 038: Frontend Modular Refactor

The `hbc-panel.js` file has grown into a monolithic "God Component" spanning ~900 lines of code. This refactor splits the UI into four logical Web Component modules. This reduces technical debt and makes the injection of the upcoming "Synthetic Outlook" tab (and any future UI modifications) extremely straightforward and contained.

## Proposed Changes

### Phase 1: Component Extraction

Ensure each new module imports `LitElement` and registers itself natively within the browser window.

#### [NEW] `frontend/hbc-dashboard.js`
- Extracts the `_renderDashboard()` function.
- Takes `data` as a property.
- Contains the `flow-grid` and `status-grid` rendering logic along with their CSS.
- Implements the `<hbc-dashboard>` custom element.

#### [NEW] `frontend/hbc-sensors.js`
- Extracts the `_renderSensors()` function.
- Takes `data` as a property.
- Handles the local expand/collapse state for the diagnostic list.
- Implements the `<hbc-sensors>` custom element.

#### [NEW] `frontend/hbc-plan-table.js`
- Extracts the massive `_renderPlan()`, `_calculateSummaryStats()`, `_toggleCol()`, and `_switchResolution()` functions.
- Takes `data_plan` as a property.
- Handles mathematical chunking for 30-minute block boundaries and table rendering.
- Handles the state management for `localStorage` (hidden columns).
- Implements the `<hbc-plan-table>` custom element.

### Phase 2: The Orchestrator

#### [MODIFY] `frontend/hbc-panel.js`
- Strip all rendering logic.
- Import the new sub-components at the top of the file:
  ```javascript
  import "./hbc-dashboard.js";
  import "./hbc-sensors.js";
  import "./hbc-plan-table.js";
  ```
- Retain the HA `fetchWithAuth()` polling logic, tab-switching state, and top toolbar rendering.
- The `render()` function now simply distributes the network data to the sub-components:
  ```javascript
  ${this._activeTab === "dashboard"
      ? html`<hbc-dashboard .data=${this._data}></hbc-dashboard>
             <hbc-sensors .data=${this._data}></hbc-sensors>`
      : html`<hbc-plan-table .data=${this._data}></hbc-plan-table>`}
  ```
