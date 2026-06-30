# Implementation Tasks: Solver Tolerance

## Feature: 057-solver-tolerance

### Phase 1: Foundational Setup
- [x] T001 Define `SOLVER_TOLERANCE_KWH = 0.1` constant in `custom_components/house_battery_control/const.py`

### Phase 2: [US1] Guard Deadline Float Precision (TDD)
- [x] T002 [US1] Create test `test_lin_fsm_float_precision_guard` in `tests/test_lin_fsm.py` simulating exact strict bounds that cause infeasibility.
- [x] T003 [US1] Run `pytest tests/test_lin_fsm.py` to confirm `test_lin_fsm_float_precision_guard` FAILS.
- [x] T004 [US1] Modify `custom_components/house_battery_control/fsm/lin_fsm.py` (around line 215) to apply `- SOLVER_TOLERANCE_KWH` to `max_reachable`.
- [x] T005 [US1] Run `pytest tests/test_lin_fsm.py` to confirm `test_lin_fsm_float_precision_guard` PASSES.

### Phase 3: [US2] Reserve SoC Float Precision (TDD)
- [x] T006 [US2] Create test `test_lin_fsm_float_precision_reserve` in `tests/test_lin_fsm.py` simulating exact strict bounds for `reserve_soc` limits.
- [x] T007 [US2] Run `pytest tests/test_lin_fsm.py` to confirm `test_lin_fsm_float_precision_reserve` FAILS.
- [x] T008 [US2] Modify `custom_components/house_battery_control/fsm/lin_fsm.py` (around line 201) to apply `- SOLVER_TOLERANCE_KWH` to `safe_lb` if `physically_accessible < reserve_kwh`.
- [x] T009 [US2] Run `pytest tests/test_lin_fsm.py` to confirm `test_lin_fsm_float_precision_reserve` PASSES.

### Phase 4: Final Validation
- [x] T010 Run `pytest tests/` to ensure no regressions in existing tests.
- [x] T011 Run `flake8` and `mypy` on modified files for static analysis compliance.
