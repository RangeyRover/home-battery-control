# Tasks: Online Analog DB Method

This document tracks the tasks required to implement the Online Analog DB Method feature (`044-json-number-44`).

## Dependencies

- Phase 1 must be completed before Phase 2.
- Phase 2 must be completed before Phase 3.
- TDD strictly required (Phase 1 first).

## Phase 1: Test Integration [US1]

Goal: Set up the local test framework to mock the HA SQLAlchemy Engine.

- [x] T001 [US1] Rename/Refactor `tests/test_analog_db.py` to `tests/test_online_analog_db.py` or create a new test file that injects a mocked HA `recorder` Engine wrapper.
- [x] T002 [US1] Implement a MockEngine class in the test suite that simulates `session.execute(text(...))` by passing the SQL string back to the real `aiosqlite` connection on `tests/test_data/home-assistant_v2.db`. This allows `rates_predictor.py` to be tested identically to production but hitting the local test database file.
- [x] T003 [US1] Validate that the test suite runs and fails (since `rates_predictor.py` does not yet use SQLAlchemy `text()`).

## Phase 2: Logic Transfer [US1]

Goal: Replace `statistics_during_period` with raw SQLAlchemy queries in `rates_predictor.py`.

- [x] T004 [US1] In `rates_predictor.py`, import `sqlalchemy.text` and obtain the SQLAlchemy engine using `get_instance(self._hass).engine`.
- [x] T005 [US1] Replace the `lts_stats` extraction loop for Solcast with the proven `SELECT start_ts, max, mean, state FROM statistics` query using `session.execute()`.
- [x] T006 [US1] Replace `extract_day_curve` equivalent (`get_lts_curve` and `get_significant_states` fallbacks) with the proven SQL query. Ensure the mapping to 288-interval float arrays is identical to the local method.
- [x] T007 [US1] Apply the graceful degradation fix: if `len(candidate_days) < 5`, ensure it falls back to the top 5 closest matches by sorting by error.
- [x] T008 [US1] Ensure all blocking database operations inside `_run_analog_search` are fully compatible with `async_add_executor_job` from the parent coordinator.

## Phase 3: Polish & Validation [US1]

Goal: Prove everything works successfully.

- [x] T009 [US1] Run the refactored test suite to verify 100% pass rate.
- [x] T010 [US1] Run `ruff check --fix` across the affected files.
- [ ] T011 [US1] Commit changes to the `044` branch.
