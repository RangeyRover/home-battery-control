# Implementation Plan: Telemetry API Split

**Branch**: `050-telemetry-api-split` | **Date**: 2026-04-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/050-telemetry-api-split/spec.md`

## Summary

This feature resolves the 1MB data payload bloat caused by the legacy `/hbc/api/status` endpoint. By creating a lightweight `/hbc/api/telemetry` endpoint (for background polling) and a `/hbc/api/plan` endpoint (columnar, deduplicated 30-min arrays), we will reduce idle background network transfer by over 99%, making the dashboard mobile-data friendly.

## User Review Required

> [!WARNING]
> **API Contracts & Breaking Changes**: We will introduce two new endpoints (`/hbc/api/telemetry` and `/hbc/api/plan`). The existing `/hbc/api/status` endpoint will be preserved for debugging, but the JS frontend will migrate entirely to the new endpoints. Please review the Proposed Changes to ensure the new payloads provide everything you need.

## Open Questions

> [!IMPORTANT]
> 1. Should we strip out the `attributes` dictionary from sensors exposed on the debug endpoint (`/hbc/api/status`) as well, or leave that 1MB payload entirely untouched for pure 1:1 legacy debugging?
> 2. The 30-minute default for the `plan` payload is great, but do we need the frontend `hbc-plan-table.js` to lazy-load the 5-minute payload via a query parameter `?resolution=5min` when the user clicks the "5 Min" toggle? Or should we just push the 5-min array anyway (which in columnar form is ~15-20KB) and let the JS filter it locally?

## Proposed Changes

---

### Backend API (`web.py` & `__init__.py`)

#### [MODIFY] [web.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/web.py)
- Create `HBCApiTelemetryView(HomeAssistantView)` returning only core variables:
  - `soc`, `solar_power`, `grid_power`, `battery_power`, `load_power`
  - `state`, `reason`, `limit_kw`, `target_soc`
  - `acquisition_cost`, `cumulative_cost`, `current_price`
- Create `HBCApiPlanView(HomeAssistantView)` returning the plan arrays. Will accept `?resolution=30min` (default) or `?resolution=5min`.
- Modify `HBCApiStatusView` to strip `attributes` from the `sensors` payload to prevent massive HA weather object duplication.

#### [MODIFY] [\_\_init\_\_.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/__init__.py)
- Register `HBCApiTelemetryView` and `HBCApiPlanView` in HA.

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

#### [MODIFY] [hbc-panel.js](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-panel.js)
- Change `_fetchData()` to fetch `/hbc/api/telemetry` instead of `/hbc/api/status`.
- Pass `telemetry` down to the child components (`hbc-dashboard`).
- When the active tab changes to `plan` or `outlook`, trigger a one-off fetch to `/hbc/api/plan` and cache it.

#### [MODIFY] [hbc-plan-table.js](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/frontend/hbc-plan-table.js)
- Update data parsing logic to map the new columnar `columns` and `rows` arrays into the UI rendering logic.
- If the 5-min toggle is clicked, fetch the `/hbc/api/plan?resolution=5min` endpoint dynamically.

## Verification Plan

### Automated Tests
- `pytest tests/ -v` to ensure no existing diagnostic paths break.
- Add a test asserting that `/hbc/api/telemetry` is < 2KB.

### Manual Verification
- Deploy to HA and open browser dev tools (Network tab).
- Verify the background polling request is targeting `/hbc/api/telemetry` and size is < 5KB.
- Click the Plan tab and verify `/hbc/api/plan` is fetched.
