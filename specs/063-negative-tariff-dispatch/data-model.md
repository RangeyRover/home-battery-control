# Physical and economic data model

## Approved scope amendment — 2026-10-12

The user approved implementation, then explicitly limited it to calculation changes and required Spec Kit task decomposition followed by SDD/TDD (tests before code). Powerwall mode scripts, executor behaviour, service payloads and command lifecycle remain unchanged. Script capability certification, rate control, watchdogs and new dispatch plumbing are excluded from this feature. Earlier wording requiring those changes is superseded by this amendment. First-state protection belongs in the calculation adapter, using its current price input; this does not claim continuous live enforcement between updates.

Economic policy remains: never recommend deliberate battery export at a nonpositive effective price; allow additional later negative-price solar export when the whole forecast sequence saves money. Forecasts are estimates, not a guarantee of actuator power or realised savings. Existing input price units are retained consistently; no speculative migration of stored accounting values.


All interval flows are AC-side kWh; B is stored battery kWh. Inputs include interval duration, load L, available PV P, signed buy/sell tariffs, charge/discharge efficiency, capacity, reserve, physical power limits, source timestamps/units and coverage flags.

Let H=min(P,L), S=P-H and R=L-H. H is PV serving household load. Variables are grid-to-home gh, grid-to-battery gc, PV-to-battery pc, PV-to-grid px, battery-to-home dh and battery-to-grid dx, all nonnegative.

Exact constraints:

```
gh + dh = R
pc + px = S
I = gh + gc
X = px + dx
C = pc + gc
D = dh + dx
I + P + D = L + C + X
B[t+1] = B[t] + eta_charge*C - D/eta_discharge
0 <= B <= capacity (plus feasible reserve policy)
C <= charge_kw*dt
D <= discharge_kw*dt
```

Binary direction constraints enforce C=0 or D=0 and I=0 or X=0, using tight finite bounds calculated from load/PV and power limits. These are instantaneous net-meter modes, not gross flows that can be credited simultaneously. Physical power limits remain model inputs; mode execution is unchanged. No curtailment exists: S must all enter pc or px.

For sell <= 0 OR sell <= export_margin: dx=0. px remains available, so unavoidable solar export does not cause infeasibility. PV serves load first; the model cannot relabel battery export as household supply while exporting that same household's PV.

Cash[t] = buy[t]*I[t] - sell[t]*X[t]. Negative sell increases cash cost. Forecast negative-export charge = sum(max(-sell,0)*X). Degradation and terminal inventory valuation are separate components. Export margin, if included in preference scoring, applies to battery exports only and is not reported as retailer cash expenditure.

Terminal treatment is identical for candidate/reference. Report delta cash, delta terminal inventory value and delta policy/degradation components independently; match terminal B in hand-verifiable regression examples. Never value unavailable future demand as a certain realised saving.

Trajectory validator checks finite values, bounds, binaries, conservation, efficiencies, price policy and physical flow feasibility before extraction/dispatch. Proposed residual tolerance: 1e-6 kWh, verified against solver numerics; currency comparison tolerance 1e-6 currency units, with no market-price epsilon that changes signs. Existing SOLVER_TOLERANCE_KWH=0.1 is not an acceptable energy-conservation allowance.

Acquisition accounting starts from B[0]=capacity*soc_fraction. Track stored energy and inventory value consistently; grid charge cost is gc*buy. Any solar inventory accounting is explicitly defined separately from real meter cash. Zero stored energy must not divide by zero. Do not change SoC to satisfy accounting policy.

The test fixture records price source timestamps and assumptions. Runtime forecast provenance is not changed within the calculation-only scope; a padded array is not proof of fresh coverage.


---

## US4 & US5 entities (2026-10-12 / 2026-11-09)

### SolverStats (per calculation)

| Field | Type | Meaning / validation |
|---|---|---|
| `solve_seconds` | float >= 0, 3 dp | Wall time from entry of `propose_state_of_charge` to return (monotonic clock) |
| `budget_seconds` | float in [1, 60] | Effective budget after clamping |
| `passes` | int >= 0 | Number of `linprog` calls made (0 for invalid inputs) |
| `integer_used` | bool | Any pass ran with integer direction variables |
| `reference_solve` | bool | Negative-price comparison solve was started |
| `outcome` | `"optimal"` \| `"timeout"` \| `"no_plan"` | `optimal`: valid trajectory returned within budget; `timeout`: budget reached (`remaining <= 0` or solver time limit); `no_plan`: invalid inputs or infeasible trajectory |
| `detail` | str <= 120 chars | Human-readable reason, e.g. `"Solver time budget reached"` |
| `horizon_steps` | int | Number of 5-minute steps solved |

Invariants: `outcome in ("timeout", "no_plan")` <=> empty plan. `outcome == "optimal"` <=> non-empty validated plan. Stats are produced on every return path.

### RateInterval spike flag & RenewablesGuard

- `RateInterval.spike: bool` — `True` when `spike_status in ("potential_spike", "spike")` or `descriptor == "spike"`.
- `RenewablesGuard.spike_triggered: bool` — `True` when any interval in `rates[:144]` has `spike == True`.
- `RenewablesGuard.target_soc: float` — `80.0` when active only via `spike_triggered`; `100.0` when low-renewables/Solcast triggered.
- `LinearBatteryController.guard_target_soc: float` — default `100.0`; caps `reachable` at `capacity * (guard_target_soc / 100.0)` for `guard_deadline_steps`.

### Coordinator-level additions

- `solver_stats`: last SolverStats (dict) in coordinator `data`, debug snapshot (`solver_snapshot.result.solver_stats`) and telemetry payload.
- `solve_seconds_max_24h`: max `solve_seconds` over a deque of `(utc_time, solve_seconds)` pruned to 24 h (in-memory; resets on restart).

### Config

- `solver_time_budget` (float, default 30.0, min 1.0, max 60.0, step 1) — passed to the FSM via `fsm_context.config["solver_time_budget"]`; adapter clamps to [1, 60].
- `DEFAULT_GUARD_DAYTIME_DEADLINE = "16:00"`.

### Dashboard status colour rule

- Green: `optimal` and `solve_seconds < min(5 s, 0.5 * budget)`.
- Amber: `optimal` otherwise (slower than a few seconds — a performance warning, plan still optimal).
- Red: `timeout` or `no_plan` (also raises a constraints-bar badge).
