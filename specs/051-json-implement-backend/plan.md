# Implementation Plan: Server-Side Plan Matrix Aggregation

**Feature**: 051-json-implement-backend  
**Author**: Antigravity  

## Technical Context

The frontend `hbc-plan-table-lite.js` previously fetched a 128KB 5-minute matrix and filtered it to 30-minute intervals locally. This completely circumvented the bandwidth reduction goal for the plan matrix. To fix this, we must shift the aggregation logic back into the Python backend (`coordinator.py` -> `_build_plan_matrix` via `diagnostics.py` -> `build_plan_matrix` or locally).

## Proposed Changes

### Phase 1: Backend Aggregation Logic
#### [MODIFY] `custom_components/house_battery_control/coordinator.py`
- Update `_build_plan_matrix()` to accept an optional `resolution` parameter.
- Add an internal loop or helper method that chunks the `table` array of dictionaries (the output of `build_diagnostic_plan_table`).
- If `resolution == "30min"` (the default), group rows up to the 30-minute boundaries (times ending in `:25` or `:55`).
- Calculate averages for continuous rates (`Import Rate`, `Export Rate`, `Net Grid`, `PV Forecast`, `Load Forecast`, `Air Temp Forecast`, `Temp Delta`, `Load Adj.`, `Acq. Cost`).
- Extract the last row's cumulative values for `SoC Forecast` and `Cumul. Cost`.
- Sum the `Interval Cost`.
- Elevate `FSM State` and `Inverter Limit` to `CHARGE_GRID` or `DISCHARGE_GRID` if any row in the chunk contains active grid commands; otherwise fallback to `SELF_CONSUMPTION`.

#### [MODIFY] `custom_components/house_battery_control/web.py`
- Modify `HBCApiPlanView.get` to read the query parameter: `resolution = request.query.get("resolution", "30min")`.
- Pass this string directly to `coord._build_plan_matrix(resolution=resolution)`.

### Phase 2: Frontend Explicit Fetching
#### [MODIFY] `custom_components/house_battery_control/frontend/hbc-plan-table-lite.js`
- Change `_fetchPlan()` to dynamically append `?resolution=${this._planResolution}` to the fetch URL.
- Modify the `_switchResolution` function so it updates `_planResolution` and then explicitly calls `_fetchPlan()` rather than simply triggering a local re-render.
- Delete the complex `else { let currentChunk = []; ... }` chunking logic inside `render()`, because the backend now delivers perfectly formatted data. The `rows` variable will map 1:1 regardless of the chosen resolution.

## Constitution Check
- No destructive changes to the legacy `/hbc/api/status` endpoint.
- Aligns with the core principle of minimizing the default Home Assistant background footprint.

## Verification Plan
1. **Payload Size**: Verify the `/hbc/api/plan` JSON response length is under 20KB.
2. **5-Min Request**: Verify `/hbc/api/plan?resolution=5min` returns the full 128KB payload.
3. **Frontend Regression**: Verify the UI table columns remain identical and render correctly.
