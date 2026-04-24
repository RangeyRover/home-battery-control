# Task Breakdown: Coordinator Strangler Pattern

**Feature Branch**: `042-coordinator-strangler`  
**Created**: 2026-04-19  
**Status**: Ready  
**Input**: Generated from `spec.md` and `plan.md`

## Implementation Strategy

We will use the Strangler Fig pattern to incrementally extract logic from `coordinator.py` into focused modules. The integration must remain fully functional and tests must pass at every step.

## Dependencies

- All phases are linear to ensure the strangler pattern works safely.

## Phase 1: Setup

Goal: Initialize the new modules and verify tests pass before changing `coordinator.py`.

- [x] T001 Create `custom_components/house_battery_control/diagnostics.py` with empty skeleton functions.
- [x] T002 Create `custom_components/house_battery_control/context_builder.py` with empty skeleton functions.
- [x] T003 Ensure `__init__.py` or module imports are clean and `pytest` still passes.

## Phase 2: Foundational - Diagnostics Extraction

Goal: Remove string-heavy UI formatting from the coordinator.

- [x] T004 [US1] Move `_build_diagnostic_plan_table` logic from `coordinator.py` to `diagnostics.build_diagnostic_plan_table`.
- [x] T005 [US1] Move `_build_sensor_diagnostics` logic from `coordinator.py` to `diagnostics.build_sensor_diagnostics`.
- [x] T006 [US1] Update `coordinator.py` to call the new `diagnostics` module functions instead of its own methods.
- [x] T007 [US1] Run `pytest` to ensure the diagnostic extraction hasn't broken any tests.

## Phase 3: Foundational - Context Builder Extraction

Goal: Remove FSM context construction logic.

- [x] T008 [US1] Move `_build_solver_inputs` logic from `coordinator.py` to `context_builder.build_solver_inputs`.
- [x] T009 [US1] Move the solar forecast alignment and array padding from `_async_update_data` to `context_builder.align_forecasts`.
- [x] T010 [US1] Update `coordinator.py` to delegate LP inputs construction to `context_builder.py`.
- [x] T011 [US1] Run `pytest`. to ensure solver inputs match previous behavior exactly.
- [x] T012 [US1] Run `ruff check --fix` and `black` (or standard formatter) to ensure the extracted modules meet style guidelines.
- [x] T013 [US1] Verify that `coordinator.py` shrinkage goal is met (measure before/after line counts).
- [x] T014 [US1] Run the full `pytest` suite across the whole integration to guarantee 100% regression-free extraction.

## Phase 4: Polish & Cross-Cutting Concerns

Goal: Clean up, lint, and verify operational stability.

- [ ] T012 Run `ruff check --fix` on `coordinator.py`, `diagnostics.py`, and `context_builder.py`.
- [ ] T013 Perform manual verification of integration boot and Synthetic/Diagnostic UI generation.
- [ ] T014 Commit and push changes.
