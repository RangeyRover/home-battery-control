# Implementation Plan: Visualizing Synthetic Forecast Transition

## Proposed Changes

### 1. Backend (`diagnostics.py`)
Currently, the `extended_rates_timeline` in the coordinator marks synthetic intervals with `"synthetic": True`. We will extract this flag when building the diagnostic table.
- **[MODIFY]** `custom_components/house_battery_control/diagnostics.py`: 
  - In the `table.append` call, add `"Synthetic": rate.get("synthetic", False)`.

### 2. Frontend (`hbc-plan-table.js`)
We will read this flag and apply visual indicators to the Plan Table rows.
- **[MODIFY]** `custom_components/house_battery_control/frontend/hbc-plan-table.js`:
  - Extract the `Synthetic` flag for both `5min` and `30min` resolution rows.
  - If a row is synthetic, append a subtle `*` to the `Local Time` (e.g., `15:30*`).
  - Add a CSS class `state-synthetic` to the table row (`<tr>`), which we can use to slightly dim the row text or apply a distinct border (optional, but good for structure).
  - Add a small legend to the bottom of the table (in the footer row or near the bottom buttons) explaining: `* Synthetic Forecast Period`.

## Verification Plan
1. **Automated tests**: Ensure `test_coordinator.py` and `test_fsm_lin.py` continue to pass.
2. **Frontend check**: Run the system locally and verify the `*` appears on the table starting from the synthetic boundary.
