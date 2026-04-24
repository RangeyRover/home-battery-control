# Implementation Plan: Local Analog Testing & TDD

This plan outlines the approach to strictly prove the analog search logic locally against the SQLite test database (`tests/test_data/home-assistant_v2.db`) for a sweep of target PV yields before implementing the fixes in the online `rates_predictor.py`.

## Proposed Changes

### 1. Build Local TDD Sweep Script
We will create a pure Python testing script that executes the raw extraction logic against the SQLite database. This ensures the SQL and timezone math is flawless outside the complexity of the Home Assistant event loop.

#### [NEW] `tests/test_analog_sweep.py`
- Setup a test connecting to `tests/test_data/home-assistant_v2.db`.
- Implement `test_analog_sweep` parameterized with `[28, 26, 24, 22, 20, 18, 16, 14]`.
- Implement the exact analog search method, fixing the timezone UTC conversion bug to ensure `forecast_date` matches the local timezone, not UTC.
- Assert that exactly 5 days are returned for every target, proving the 5% tolerance and graceful degradation fallback.

### 2. Transfer Proven Logic to Online Build
Once the sweep passes locally, we will port the corrected logic directly into the integration.

#### [MODIFY] `custom_components/house_battery_control/rates_predictor.py`
- Port the corrected `_run_analog_search` logic.
- Fix the timezone shift in `_get_lts_curve` (`dt_util.as_local(dt)`).
- Restore the `history.get_significant_states` fallback to ensure Amber prices (which lack `statistics` records) are successfully extracted instead of flatlining.

### 3. Final Integration Validation
We will update the existing `test_online_analog_db.py` to include the same sweep of targets (28 to 14) running through the mocked HA environment to guarantee zero regressions.

## Verification Plan

### Automated Tests
1. Run `pytest tests/test_analog_sweep.py -v -s` to explicitly print the 5 selected dates for each of the 8 targets, proving the logic locally.
2. Run `pytest tests/test_online_analog_db.py -v` to prove the HA wrapper integration is flawless.

### Manual Verification
Deploy to the live instance and verify Tomorrow's Outlook renders without tracebacks or flatlined curves.
