# Implementation Plan: Solar Today Guard Trigger (056)

## Context

Feature 055 (Low Renewables Guard) currently evaluates two triggers:
1. Amber Express renewables % (12-hour average)
2. Solcast **tomorrow** forecast (kWh)

This amendment adds a third trigger: **Solcast today** forecast. When today's solar is low, the guard activates to charge the battery before the evening peak.

The change is surgical — 3 files modified, 0 new files, no new config fields (shared threshold).

## Proposed Changes

### Guard Logic

#### [MODIFY] [renewables_guard.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/renewables_guard.py)

- Add `solcast_today: float` parameter to `evaluate()`
- After the existing Solcast tomorrow check (line 73-78), add a parallel Solcast today check using the **same** threshold (`solcast_target_kwh`)
- Append `"Solcast Today (X.X <= Y.Y kWh)"` to `trigger_reasons` when fired
- Update the trigger mode logic (line 80-86): in OR mode, any of the 3 triggers fires; in AND mode, all 3 must fire
- **AND mode consideration**: The AND condition currently requires `amber_triggered and solcast_triggered`. With 3 triggers, AND should require all configured/available triggers to fire. If Solcast today is unavailable (0.0 sentinel), skip it in AND evaluation.

### Coordinator Wiring

#### [MODIFY] [coordinator.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/coordinator.py)

- At line ~484, alongside the existing `solcast_tomorrow` read, add a `solcast_today` read using `CONF_SOLCAST_TODAY_ENTITY` / `DEFAULT_SOLCAST_TODAY`
- Pass `solcast_today=solcast_today` to `self.renewables_guard.evaluate()`

### Test Updates

#### [MODIFY] [test_renewables_guard.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_renewables_guard.py)

- Update all existing `evaluate()` calls to include `solcast_today` parameter (default to high value so they don't change behaviour)
- Add new tests:
  - `test_guard_today_solar_triggers_alone` — low today, high tomorrow, high renewables → guard active in OR mode
  - `test_guard_today_solar_high_no_trigger` — high today → no trigger from today
  - `test_guard_and_mode_all_three` — AND mode requires all 3
  - `test_guard_and_mode_today_missing` — AND mode, today unavailable, skipped gracefully
  - `test_guard_or_mode_today_only` — only today fires, guard active

#### [MODIFY] [test_coordinator.py](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_coordinator.py)

- Update existing guard coordinator tests to include Solcast today entity mock
- Add `test_coordinator_guard_today_solar_trigger` — mock low Solcast today, verify guard activates

## Verification Plan

### Automated Tests
```bash
pytest tests/test_renewables_guard.py tests/test_coordinator.py -v
pytest tests/ -v  # Full regression
ruff check custom_components/ tests/
```

### Manual Verification
- Deploy to HA, set Solcast today entity to a low value, observe guard badge
