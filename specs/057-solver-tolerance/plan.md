# Implementation Plan: Solver Tolerance

## Technical Context
- **Codebase:** `custom_components/house_battery_control/fsm/lin_fsm.py`
- **Dependency:** `scipy.optimize.linprog`
- **Issue:** Strict bound constraints (`min/max` equality tests) applied via mathematically calculated sums fail due to IEEE 754 float precision inside the simplex/interior-point matrices.

## Constitution Check
- **TDD:** Write a failing test ensuring tight constraints fail, then apply the epsilon fix.
- **Speckit Compliance:** The spec enforces robust math without altering business logic.
- **Safety:** Adds tolerance that physically translates to fractions of a Watt-hour, well below the physical precision of battery inverter sensors (which typically have 1-5% error).

## Proposed Changes

### Phase 1: Implement Float Precision Tolerance
#### [MODIFY] `custom_components/house_battery_control/fsm/lin_fsm.py`
- Introduce a mathematical epsilon (`0.1` = 100 Wh) to lower bounds in `lin_fsm.py` when calculating `max_reachable` for `guard_deadline_steps`.
- Specifically, update:
  ```python
  new_lb = max(current_lb, max_reachable - 0.1)
  ```
- Also update the general reserve SoC bounding logic to prevent float drift crashes when the battery hits its minimum limit:
  ```python
  if physically_accessible < reserve_kwh:
      safe_lb = max(0.0, safe_lb - 0.1)
  ```

### Phase 2: Testing
#### [MODIFY] `tests/test_lin_fsm.py`
- Create `test_lin_fsm_float_precision_guard` to test `propose_state_of_charge`.
- Pass a scenario where the battery requires *exactly* maximum charge capacity per step to reach a strict deadline SoC.
- Verify that without the fix, it is infeasible or errors, and with the fix, it resolves normally.

## Verification Plan
1. **Automated Tests:** Execute `pytest tests/test_lin_fsm.py` to ensure all original tests pass and the new precision test succeeds.
2. **Dashboard Verification:** The integration will stop producing `0.00` fallback values for the plan because `future_plan` will no longer be an empty array due to solver crashing.
