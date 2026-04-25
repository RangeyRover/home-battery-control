# Implementation Plan: Telemetry API Split

**Branch**: `050-telemetry-api-split` | **Date**: 2026-04-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/050-telemetry-api-split/spec.md`

## Summary

This feature resolves the 1MB data payload bloat caused by the legacy `/hbc/api/status` endpoint. By creating a lightweight `/hbc/api/telemetry` endpoint (for background polling) and a `/hbc/api/plan` endpoint (columnar, deduplicated 30-min arrays), we will reduce idle background network transfer by over 99%, making the dashboard mobile-data friendly.

## User Review Required

> [!WARNING]
> **API Contracts & Breaking Changes**: We will introduce two new endpoints (`/hbc/api/telemetry` and `/hbc/api/plan`). The existing `/hbc/api/status` endpoint will be preserved for debugging, but the JS frontend will migrate entirely to the new endpoints. Please review the Proposed Changes to ensure the new payloads provide everything you need.

## Resolved Decisions

1. **Debug Payload**: The `/hbc/api/status` endpoint will remain **100% untouched** and continue to serve the 1MB payload with all sensor attributes and labels.
2. **5-Min Payload**: The new frontend will strictly lazy-load the 5-min array only when the user explicitly clicks the "5 Min" toggle. The primary goal is minimizing total KB moved.
3. **Frontend Split**: We will create a new, lightweight `hbc-panel-lite.js` for production at `/hbc-panel`. The existing heavy `hbc-panel.js` will be preserved and exposed at a new `/hbc-debug` URL in Home Assistant's sidebar.
4. **Outlook Lazy Load**: "Tomorrow's Outlook" is very heavy (~244KB for `state_transitions`). The new frontend will not load this automatically; it will be an explicit button to fetch it.
5. **Debug Link**: An inconspicuous link will be added to the new dashboard to allow developers to quickly hop to the `/hbc-debug` view.

## Proposed Changes

---

### Backend API (`web.py` & `__init__.py`)

#### [MODIFY] [web.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/web.py)
- Create `HBCApiTelemetryView(HomeAssistantView)` returning only core variables:
  - `soc`, `solar_power`, `grid_power`, `battery_power`, `load_power`
  - `state`, `reason`, `limit_kw`, `target_soc`
  - `acquisition_cost`, `cumulative_cost`, `current_price`
- Create `HBCApiPlanView(HomeAssistantView)` returning the plan arrays. Will accept `?resolution=30min` (default) or `?resolution=5min`.
- Create `HBCApiOutlookView(HomeAssistantView)` returning only the `state_transitions` array for lazy-loading.

#### [MODIFY] [\_\_init\_\_.py](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/__init__.py)
- Register `HBCApiTelemetryView` and `HBCApiPlanView` in HA.
- Register a second sidebar panel `hbc-debug` pointing to the legacy frontend.
- Update the default `hbc-panel` to point to the new lightweight frontend.

---

### Backend Data Preparation (`coordinator.py` & `diagnostics.py`)

#### [MODIFY] [coordinator.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/coordinator.py)
- Add `_build_telemetry_payload()` method.
- Add `_build_plan_matrix()` method.

#### [MODIFY] [diagnostics.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/diagnostics.py)
- Refactor the plan table generator to output a columnar matrix format. Example:
  ```json
  {
    "columns": ["Time", "Local Time", "Import Rate", "FSM State", "Synthetic"],
    "rows": [
      ["15:00", "15:00", 0.15, "CHARGE_GRID", false],
      ...
    ]
  }
  ```

---

### Frontend UI (`frontend/`)

#### [NEW] [hbc-panel-lite.js](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-panel-lite.js)
- Create a new root component for the lightweight production dashboard.
- Fetches `/hbc/api/telemetry` instead of `/hbc/api/status`.
- Passes `telemetry` down to the child components.
- Adds an inconspicuous link (e.g. a small bug icon in the toolbar or footer) pointing to `/hbc-debug`.
- When the active tab changes to `plan`, triggers a one-off fetch to `/hbc/api/plan` and caches it.

#### [NEW] [hbc-outlook-lite.js](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-outlook-lite.js)
- Implement an explicit "Load Outlook" button.
- Only fetches the heavy `/hbc/api/outlook` API when clicked.

#### [NEW] [hbc-plan-table-lite.js](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-plan-table-lite.js)
- Create a lightweight table component that parses the new columnar `columns` and `rows` arrays.
- If the 5-min toggle is clicked, strictly lazy-loads the `/hbc/api/plan?resolution=5min` endpoint dynamically.

#### [MODIFY] [hbc-panel.js](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-panel.js)
- No functional changes. This remains untouched to serve the `/hbc-debug` panel.

## Verification Plan

### Automated Tests
- `pytest tests/ -v` to ensure no existing diagnostic paths break.
- Add a test asserting that `/hbc/api/telemetry` is < 2KB.

### Manual Verification
- Deploy to HA and open browser dev tools (Network tab).
- Verify the background polling request is targeting `/hbc/api/telemetry` and size is < 5KB.
- Click the Plan tab and verify `/hbc/api/plan` is fetched.
