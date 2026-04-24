# Implementation Plan: Coordinator Strangler Pattern

## Goal Description
The `coordinator.py` file has become a monolith (806 lines) handling HA integration plumbing, cost tracking, FSM context building, complex diagnostic table rendering, and solver invocation. We will employ the Strangler Fig pattern to systematically extract these distinct responsibilities into specialized modules while maintaining 100% of existing functionality and test coverage. This will shrink `coordinator.py` dramatically and make the codebase far easier to maintain.

## User Review Required
> [!IMPORTANT]
> The strangler pattern works best when done incrementally. The proposed plan creates two new modules (`diagnostics.py` and `context_builder.py`). Do you approve of these module names and this logical separation?

## Proposed Changes

### `custom_components/house_battery_control`

#### [NEW] `diagnostics.py`
Create a new module to handle the heavy string manipulation and formatting logic currently buried in the coordinator.
- Move `_build_diagnostic_plan_table` logic into a pure function `build_diagnostic_plan_table(fsm_result, start_time, rates_timeline)`.
- Move `_build_sensor_diagnostics` into a pure function `build_sensor_diagnostics(coordinator_state, config)`.

#### [NEW] `context_builder.py`
Create a new module to encapsulate the complex logic of aligning solar and load forecasts to the pricing timeline and constructing the `FSMContext`.
- Extract the logic in `_async_update_data` that builds `aligned_solar`, handles `fallback_len`, and initializes `FSMContext`.
- Extract `_build_solver_inputs` into `build_solver_inputs(fsm_context)`.

#### [MODIFY] `coordinator.py`
Strangle the existing monolithic methods by replacing their bodies with delegation calls to the new modules:
- Refactor `_build_diagnostic_plan_table` to call `diagnostics.build_diagnostic_plan_table`.
- Refactor `_build_sensor_diagnostics` to call `diagnostics.build_sensor_diagnostics`.
- Refactor `_build_solver_inputs` to call `context_builder.build_solver_inputs`.
- Clean up `_async_update_data` so it reads like a high-level orchestrator rather than performing low-level array manipulation.

## Verification Plan

### Automated Tests
- Run `pytest` continuously. The beauty of the strangler pattern is that all existing tests in `test_coordinator.py` MUST continue to pass without modification, as the public interface of the coordinator does not change.
- `ruff check` to ensure imports are clean.

### Manual Verification
- Deploy to Home Assistant.
- Verify the House Battery Control dashboard loads successfully.
- Verify the `Synthetic Outlook` and `Diagnostic Plan` tables render correctly with no changes to their layout or data.
