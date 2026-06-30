# Feature Specification: LP Solver Tolerance and Robustness

## 1. Feature Description
The House Battery Control's Linear Programming (LP) solver occasionally "stalls" (returns an infeasible ERROR state), causing the dashboard to display 0.00 for all 24-Hour Forecast values. This stalling behavior is triggered by strict, physically absolute boundary limits calculated dynamically by the integration (e.g., when the Solar Today guard requires a 100% SoC by a tight deadline). Because the LP solver sums incremental charging operations mathematically, floating-point precision loss can cause the mathematical sum to be infinitesimally smaller than the strict absolute bound, resulting in model infeasibility. The user has requested more tolerance for the solver to prevent these stalls.

## 2. Business Value
- **Stability**: Prevents the LP solver from crashing/stalling on valid mathematical scenarios due to minute float precision drift.
- **Reliability**: Ensures the 24-Hour Forecast Summary on the dashboard remains populated instead of zeroing out.
- **Graceful Degradation**: Improves the mathematical robustness of guard bounds so that they do not over-constrain the solver unexpectedly.

## 3. User Scenarios & Testing

### Scenario 1: Guard Deadline Float Precision
**Given** the Solar Today or Low Renewables guard is active and enforces a tight timeline to reach maximum battery capacity
**When** the integration computes the theoretical max-reachable limit for the LP solver
**Then** the solver successfully calculates a plan without returning an ERROR state, even if the theoretical limit is separated from the summation capability by a floating-point margin (e.g., 1e-10).
**And** the dashboard correctly renders non-zero forecast values.

### Scenario 2: Reserve SoC Float Precision
**Given** the battery is operating normally but pushing against a high reserve SoC requirement
**When** the battery naturally discharges down to the calculated physical boundary
**Then** the solver will not crash from float precision constraints when bounding the physical bottom limit.

## 4. Functional Requirements

### 4.1 Constraint Tolerance
- **Req 4.1.1:** The integration MUST inject a mathematical epsilon (tolerance) into strict equality or boundary limits passed to the LP solver when they represent a summation of physical limits.
- **Req 4.1.2:** Specifically, the `max_reachable` bound applied during guard deadline enforcement MUST be relaxed by a small tolerance value (e.g., 0.1 kWh) to allow the SciPy `linprog` solver to find a feasible solution.
- **Req 4.1.3:** The `safe_lb` calculation protecting the battery's reserve capacity MUST similarly apply a tolerance when the physically accessible energy is lower than the requested reserve.

### 4.2 Configurable Tolerance
- **Req 4.2.1:** The system MAY (as a future enhancement or if needed by the mathematical engine) expose this tolerance value, but by default it MUST be a hardcoded reasonable constant (like 0.1 kWh) that is large enough to absorb 64-bit float summation drift but small enough to not impact battery behavior physically.

## 5. Success Criteria
- The dashboard does not show all 0.00s when the Solar Today guard is active under tight charging timelines.
- The `scipy.optimize.linprog` call inside the `lin_fsm` module no longer returns an infeasible `ERROR` state caused by precision mismatch on `bounds`.
- TDD tests demonstrate that identical precision mismatch scenarios pass with the fix.

## 6. Assumptions & Dependencies
- The root cause of the solver failure is strictly related to boundary inequality constraint mismatches induced by floating point loss in `scipy` as identified in the diagnostic logs.
- Introducing a 0.1 (100 Watt-hour) margin has zero measurable physical impact on battery wear, reporting, or tariff cost optimization.
