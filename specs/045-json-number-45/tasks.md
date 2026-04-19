# Tasks: Local Analog Testing

**Input**: Design documents from `/specs/045-json-number-45/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Verify `tests/test_data/home-assistant_v2.db` exists and has historical data covering extreme analog targets.

---

## Phase 2: User Story 1 - Local Test Verification (Priority: P1) 🎯 MVP

**Goal**: Prove the analog search algorithm logic locally against a test database before applying it to the live integration.

**Independent Test**: Can be fully tested by running `pytest tests/test_analog_sweep.py -v -s`.

### Implementation for User Story 1

- [x] T002 [US1] Create script `tests/test_analog_sweep.py` to establish SQLite connection.
- [x] T003 [US1] Port pure SQL `_run_analog_search` logic to `test_analog_sweep.py`.
- [x] T004 [US1] Add fix for timezone UTC conversion (`dt_util.as_local(dt)`) inside the test extraction loop.
- [x] T005 [US1] Parameterize the test to sweep target yields: `[28, 26, 24, 22, 20, 18, 16, 14]`.
- [x] T006 [US1] Assert that exactly 5 matching days are extracted and printed for each sweep target, validating the absolute error fallback for missing 5% tolerance bounds.

**Checkpoint**: At this point, the local test suite proves the logic natively against SQLite without HA wrappers.

---

## Phase 3: User Story 2 - Online Implementation (Priority: P2)

**Goal**: Implement the exact same method in the online release (`rates_predictor.py`), so that the Home Assistant integration reliably generates the 48h Synthetic Outlook.

**Independent Test**: Can be verified via `test_online_analog_db.py` and live integration usage.

### Implementation for User Story 2

- [x] T007 [P] [US2] Copy the proven logic from `test_analog_sweep.py` into `custom_components/house_battery_control/rates_predictor.py`.
- [x] T008 [P] [US2] Restore `history.get_significant_states` within `_run_analog_search` for `import_curve` and `export_curve` to prevent Amber prices from flatlining when `statistics_meta` is absent.
- [x] T009 [US2] Modify `tests/test_online_analog_db.py` to include the target sweep `[28, 26, 24, 22, 20, 18, 16, 14]` against the mocked HA engine to validate the integration layer.

**Checkpoint**: Online implementation complete and tested against mocked HA engine.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Validation and Cleanup

- [x] T010 [P] Execute `pytest tests/` to confirm 100% pass rate.
- [x] T011 [P] Ensure no flake8/mypy regressions introduced by logic changes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **User Story 1 (Phase 2)**: Must complete to prove logic before Online Implementation.
- **User Story 2 (Phase 3)**: Depends on User Story 1.

### Implementation Strategy

1. Verify the DB.
2. Complete US1 to achieve TDD sweep proof.
3. Complete US2 to integrate into `rates_predictor.py`.
4. Validate.
