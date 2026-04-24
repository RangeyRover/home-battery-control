# Tasks: Synthetic DB Tests

This document tracks the tasks required to implement the Synthetic DB Tests feature (`043-synthetic-db-tests`).

## Dependencies

- Phase 1 must be completed before Phase 2.
- No parallelization limits except the order of execution inside Phase 2.

## Implementation Strategy

We will build a simple `pytest` integration test suite. Instead of mocking the entire HA environment, the test will directly use `sqlite3` or `aiosqlite` to connect to `home-assistant_v2.db` if it's available locally, and invoke `_run_analog_search` with varying kW targets. 

## Phase 1: Setup

Goal: Establish the test module structure.

- [x] T001 Create `tests/test_analog_db.py` file with basic pytest setup and environment variable configuration to locate `home-assistant_v2.db`.
- [x] T002 Write a test fixture or setup method to assert the existence of the 950MB `home-assistant_v2.db` file (and skip the suite if not present, avoiding CI failure).

## Phase 2: Analog Search Logic [US1]

Goal: Implement the test logic that proves `_run_analog_search` computes correct, 288-interval float arrays using varying inputs.

- [x] T003 [US1] Implement a mock for `recorder.get_instance(hass).async_add_executor_job` or override `_run_analog_search` to accept a raw sqlite connection if necessary, or simply test the raw SQL query string logic inside the test.
- [x] T004 [US1] Parametrize the test case across `[30, 28, 26, 24, 22, 20, 18, 16, 14]` kWh target values.
- [x] T005 [US1] Inside the test case, assert that exactly 5 distinct days are found within a 5% generation tolerance (where history permits).
- [x] T006 [US1] Assert the outputs (pricing, export, load curves) are perfectly uniform (length 288 floats) and contain no nulls or gaps.
- [x] T007 [US1] Assert the tests gracefully degrade and don't raise exceptions when historical data cannot meet the 5% tolerance window for a specific target.
- [x] T008 [US1] Run the test locally and verify it passes.

## Phase 3: Polish & Cross-Cutting Concerns

- [x] T009 Run `ruff check --fix` on `test_analog_db.py`
- [x] T010 Commit changes to the `043-synthetic-db-tests` branch.
