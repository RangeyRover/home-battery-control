# 060-complex-tou-config

## Implementation Strategy

**Objective:** Implement the Complex TOU Config feature allowing up to 10 arbitrary import and 10 export periods per day.
**Methodology:** Strict Test-Driven Development (TDD). Every implementation phase must start with failing tests.
**Incremental Delivery (MVP):** 
1. Phase 1 & 2: Set up foundational constants.
2. Phase 3: Update and validate the UI (Config Flow) and write unit tests for the 24-hour overlap/gap logic.
3. Phase 4: Upgrade the forecast generator to map these dynamic periods to the 48-hour output.

---

## Phase 1: Setup

- [x] T001 Define 60 new configuration keys (Import 1-10 start/end/price, Export 1-10 start/end/price) in `custom_components/house_battery_control/const.py`

---

## Phase 2: Foundational 

- [x] T002 Implement helper functions for validating period arrays (24h continuous, no gaps, 00:00 start/end bounds) in `custom_components/house_battery_control/config_flow.py`

---

## Phase 3: User Story 1 - Configuring Multiple Import Peaks

**Goal:** Users can accurately define multiple distinct Peak windows and Shoulder/Off-peak windows in the UI, correctly validating to exactly 24 hours.
**Independent Test Criteria:** The config flow correctly saves 10 dynamic import periods. It rejects configurations with gaps, overlaps, or periods crossing midnight.

- [x] T003 [P] [US1] Write failing config flow tests validating gap, overlap, and midnight cross rejections in `tests/test_config_flow.py`
- [x] T004 [US1] Update `async_step_fixed_tou` schema to render the 10 import periods and 10 export periods (replacing old peak/shoulder schema) in `custom_components/house_battery_control/config_flow.py`
- [x] T005 [US1] Integrate the period array validation logic into the config flow submission handler to reject invalid submissions in `custom_components/house_battery_control/config_flow.py`
- [x] T006 [US1] Run tests and verify they pass (`pytest tests/test_config_flow.py`)

---

## Phase 4: User Story 2 - Time-of-Use Export Tariffs and Forecasting

**Goal:** The `FixedTOUGenerator` parses the dynamic import and export periods correctly and generates an accurate 48-hour forecast that the rest of the integration utilizes seamlessly.
**Independent Test Criteria:** Forecast generator produces 48 hours of 5-minute blocks spanning the correctly mapped `import_price` and `export_price` for each interval.

- [x] T007 [P] [US1, US2] Write failing tests for `FixedTOUGenerator` to ensure correct 48-hour generation across varying import and export blocks, including midnight wrap-arounds over multiple days in `tests/test_fixed_tou.py`
- [x] T008 [US1, US2] Refactor `FixedTOUGenerator` to accept arrays of dictionaries for import and export blocks rather than hardcoded peak/offpeak config keys in `custom_components/house_battery_control/fixed_tou.py`
- [x] T009 [US1, US2] Update `FixedTOUGenerator.generate_forecast` and `_get_price_for_time` to properly extract both `import_price` and `export_price` dynamically in `custom_components/house_battery_control/fixed_tou.py`
- [x] T010 [US1, US2] Update `RatesManager.update` to read `export_price` from the generated fixed TOU blocks instead of defaulting to `0.0` in `custom_components/house_battery_control/rates.py`
- [x] T011 [US1, US2] Run tests and verify they pass (`pytest tests/test_fixed_tou.py`)
- [x] T012 [US1, US2] Run full integration suite (`pytest`) to ensure `rates.py` changes have not broken the Amber Electric pathwaystem-wide (`pytest`)

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T013 Update `manifest.json` and `hacs.json` to bump version for release (if applicable)

---

## Dependencies

- Phase 2 (Foundational helper logic) blocks Phase 3.
- Phase 3 (Config Flow UI & Constants) must be completed before Phase 4 can be verified in an end-to-end manner, but unit tests for generator can be written in parallel.

## Parallel Execution Opportunities

- T003 (writing UI tests) and T007 (writing generator tests) can be written in parallel independently before implementation.
