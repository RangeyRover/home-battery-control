# Tasks: Solver Synthetic Integration

## Dependencies
- Phase 1 must be completed before Phase 2.
- Phase 2 is the primary implementation.

## Implementation Strategy
We will extend the `rates_list` prior to `align_forecasts` inside `coordinator.py`. This ensures that all existing logic (including `align_forecasts` and the FSM `_build_solver_inputs` iteration) gracefully scales up to 576 elements without requiring deep refactoring.

## Phase 1: Foundational Setup
- [x] T001 Verify `spec.md` and `plan.md` completeness.

## Phase 2: User Stories

### User Story 1: Appending Synthetic Analog Data to the Solver Input
**Goal**: Allow the FSM solver to optimize across a full 48-hour window by extending the known actuals with synthesized Tomorrow's Outlook data.

- [x] T002 [US1] In `custom_components/house_battery_control/coordinator.py`, locate `_async_update_data` around line 421.
- [x] T003 [US1] Generate an `extended_rates_timeline` by iterating from the end of `rates_timeline` up to 23:55 tomorrow, appending dictionaries with `import_price`, `export_price`, and `synthetic_load_kw` populated from `synthetic_pricing_curve`, `synthetic_export_curve`, and `synthetic_load_curve`.
- [x] T004 [US1] Update `align_forecasts` invocation to use `extended_rates_timeline` instead of `rates_timeline`.
- [x] T005 [US1] Locate `_build_solver_inputs` definition around line 240.
- [x] T006 [US1] Modify `_build_solver_inputs` to use `n = len(rates_list) if rates_list else 288` instead of the hardcoded `n = 288`.
- [x] T007 [US1] Update the `load_kwh` generation loop inside `_build_solver_inputs` to fall back to `rates_list[i].get("synthetic_load_kw", 0.0) * step_hours` if `i >= len(forecast_load)` but `i < len(rates_list)`.

## Phase 3: Testing & Polish
- [x] T008 Run the pytest suite to ensure `test_fsm_lin.py` and `test_coordinator.py` still pass with dynamic `n`.
- [x] T009 Validate the live integration to confirm no errors occur and that the FSM executes over the extended horizon.
