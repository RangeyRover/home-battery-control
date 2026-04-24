# Feature Tasks: Synthetic 48h LP Solver Horizon

**Branch**: `037-synthetic-48h-forecast`
**Feature**: `specs/037-synthetic-48h-forecast/spec.md`
**Plan**: `specs/037-synthetic-48h-forecast/plan.md`

## Overview

This checklist defines the dependency-ordered tasks required to implement the Synthetic 48h LP Solver Horizon. 

---

### Phase 1: Setup & Tests

**Purpose**: Test-Driven Development foundation

- [x] T001 [US1] Create `tests/test_rates_predictor.py` and write unit tests for the `SyntheticRatesPredictor` ensuring it correctly handles Solcast drift and averages analog days.
- [x] T002 [US1] Add unit tests in `tests/test_sensor.py` for the new `hbc_synthetic_rates_diagnostic` sensor.
- [x] T003 [US2] Add unit tests in `tests/test_web.py` for the `/hbc/api/synthetic_outlook` endpoint.
- [x] T004 [US2] Update `tests/js/hbc-dashboard.test.js` (or create a new test file) to test the "Tomorrow's Outlook" tab rendering and data fetching logic.
- [x] T005 [US3] Update `tests/test_coordinator.py`, `tests/test_rates.py`, and `tests/test_load.py` to assert that 576-step arrays are correctly accepted and processed without breaking the solver.

**Checkpoint**: All tests must be written and failing (or xfail) before proceeding.

---

### Phase 2: Analog Search Engine (Backend)

**Purpose**: Implementation of the mathematical backbone and HA integration.

- [x] T006 [US1] Implement `SyntheticRatesPredictor` in `rates_predictor.py`. Include the HA SQLite executor query and mathematical averaging for the 5 analog days.
- [x] T007 [US1] Implement `sensor.hbc_synthetic_rates_diagnostic` in `sensor.py` to expose the predictor's state passively.
- [x] T008 [US2] Implement the `/hbc/api/synthetic_outlook` HTTP endpoint in `web.py` to return the analog days and synthesized pricing curves as JSON.

**Checkpoint**: Execute backend unit tests. Run `pytest tests/test_rates_predictor.py tests/test_sensor.py tests/test_web.py`.

---

### Phase 3: Diagnostic UI (Frontend)

**Purpose**: Implement the "Tomorrow's Outlook" diagnostic tab.

- [x] T009 [US2] Modify `custom_components/house_battery_control/frontend/hbc-panel.js` to render the new "Tomorrow's Outlook" tab.
- [x] T010 [US2] Add a fetch call to the new `/hbc/api/synthetic_outlook` API endpoint.
- [x] T011 [US2] Render the Statistics Pane (showing the 5 dates and variance) and the Presentation Table (synthesized pricing).

**Checkpoint**: Run `npm test` to verify the frontend components.

---

### Phase 4: LP Solver Extension (Integration)

**Purpose**: Extend the solver optimization horizon to 48 hours.

- [ ] T012 [US3] Modify `rates.py` and `load.py` to support 576-step horizons.
- [ ] T013 [US3] Update `coordinator.py` to wire the `SyntheticRatesPredictor` data into the inputs passed to the SciPy LP matrix.
- [ ] T014 [US3] Ensure input arrays are dynamically truncated to match the exact length of available Solcast data to prevent matrix dimension mismatches.

**Checkpoint**: Run the full backend test suite (`pytest tests/`) to ensure the extended horizon solves correctly without regressions.

---

### Phase 5: Verification & Polish

**Purpose**: Final system validation.

- [ ] T015 Run `pytest tests/ -v` and `npm test` to ensure 100% test pass rate.
- [ ] T016 Run `ruff check custom_components/ tests/` for static analysis.
- [ ] T017 Validate the full UI functionality manually via Home Assistant (if possible) or visually confirm component code completeness.
