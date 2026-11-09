# Implementation Plan: Negative-tariff calculations

Date: 2026-10-12. Status: implemented and verified offline.
Branch: `codex/063-negative-tariff-dispatch`.
Spec: [spec.md](spec.md). Tasks: [tasks.md](tasks.md). Evidence: [validation.md](validation.md).

## Approved scope and process

The user approved implementation, explicitly required Spec Kit tasks followed by SDD/TDD, rejected splitting the solver, and limited the change to calculations. Those decisions supersede the earlier draft's separate-module, actuator, watchdog and HA-integration proposals. Public controller/FSM signatures, calculation consumers and Powerwall mode controls remain unchanged.

Spec Kit's local Antigravity helpers were used with a feature-name override because they do not understand the codex/ branch prefix. The missing constitution and Codex skill discovery are documented in research.md; no force reinitialisation was performed.

## Implemented design

All production edits are in `custom_components/house_battery_control/fsm/lin_fsm.py`.

1. Keep the existing signed discharge variables and SciPy `linprog`/HiGHS entry point. Replace the inequality balance with exact sparse site and battery equations. Solar export is explicit and cannot be curtailed. Bound combined discharge, battery capacity and import/export flows.
2. Prohibit battery export when raw sell <= 0 or effective sell <= 0. Add an independent rejection check in the existing calculation adapter; do not change executor calls or claim enforcement between calculations.
3. Use signed meter cash once. Negative imports earn credits, negative solar exports incur charges. Preserve the existing terminal-inventory policy without the positive epsilon floor. Keep the positive-price acquisition gate by re-solving prohibited intervals rather than editing a solved trajectory.
4. Validate every successful solution against bounds, equalities, inequalities and physical direction rules. Add integer direction restrictions when the relaxation uses opposing flows. Never clip a violating solution into apparent feasibility.
5. Use a 0.1% relative MIP optimality gap and a shared 15-second solve budget. This is a bounded approximate optimum, not a guarantee of exact global optimality. For current negative-price grid charging, require its feasible objective to beat the no-current-grid-charge reference's proven lower bound. Uncertain savings choose the reference. Timeout or invalid results return no forced plan. A genuinely infeasible reference due to reserve/deadline is distinguished from timeout and labelled as a constraint action.
6. Build first target, plan states, inventory and cash from one validated trajectory. Initialise acquisition inventory in stored kWh, include charging efficiency, and remove post-solve charge clipping and SoC patching.
7. Preserve all existing plan fields and add flow diagnostics in kWh. `projected_cost` is actual horizon meter cash, excluding terminal credit and export-margin policy preference. Comparison score and cash savings are distinct fields.

## Verification

Tests preceded production code. Initial RED: 15 failed, 3 passed. Existing offline baseline: 41 passed, 2 expected failures. Additional RED/GREEN cycles covered reference timeout, optimisation-bound uncertainty, independent adapter protection and horizon performance. Final combined run: 71 passed, 2 unchanged expected failures. Lint and diff whitespace checks pass.

Recorded representative desktop timings: 288 steps 3.152 s; 576 steps 8.902 s. These are workload-specific desktop measurements, not a guarantee for every price sequence or deployment machine.

## Boundaries

Price numbers retain their existing input units consistently; no speculative provider/persisted-data migration. Reject non-finite/mismatched/negative-energy inputs. The calculation cannot infer whether an already-padded array is stale, or guarantee realised savings from forecast inputs; source provenance and live control are unchanged by user direction. The CSV replay uses observed tariff values with explicitly synthetic load/PV/SoC, not a reconstruction of measured battery behaviour.

No HA runtime validation, deployment, script changes, branch merge or remote publication was performed.


---

# Plan amendment — US4 & US5: Non-destructive solve-time visibility and Amber spike pre-charge (80% by 16:00)

Date: 2026-10-12 / 2026-11-09. Status: **approved (budget 30 s, non-destructive `lin_fsm.py`, spike pre-charge 80% by 16:00)**. Spec: [spec.md](spec.md) §Amendment US4 & US5. Research: [research.md](research.md) R-01…R-09. Data model: [data-model.md](data-model.md) §US4 & US5. Contract: [contracts/dispatch.md](contracts/dispatch.md) §US4 & US5.

## Gate check

| Gate | Result |
|---|---|
| Spec exists for the change | PASS — US4 (FR-12…18) and US5 (FR-19…22) in spec.md |
| Non-destructive `lin_fsm.py` | PASS — R1–R4 applied: NO fallback solver inside `lin_fsm.py`; only `self.time_budget_s`, `self.guard_target_soc`, and read-only counters |
| Public solver signatures unchanged | PASS — attributes + optional `FSMResult.solver_stats` field |
| No executor/script/mode-control change | PASS |
| Front end + config + translations included | PASS |

## Design

### 1. Non-destructive Solver & Adapter (`fsm/lin_fsm.py`, `fsm/base.py`)
- `LinearBatteryController.__init__`: add `self.time_budget_s = 30.0`, `self.guard_target_soc = 100.0`, and `self.last_solve_stats = {}`.
- In `propose_state_of_charge`:
  - Replace literal `15.0` with `self.time_budget_s`.
  - In the `guard_deadline_steps` loop, use `target_cap = capacity * (getattr(self, "guard_target_soc", 100.0) / 100.0)` in `reachable = min(target_cap, current + deadline * charge_limit * eta_in)`.
  - Track `passes` (incremented per `linprog` call), `integer_used` (`bool(np.any(integer_modes))`), `reference_solve` (`True` when comparison solve starts), and `timed_out` (`remaining <= 0` or HiGHS time-limit status).
  - Record `self.last_solve_stats` on every return path (`optimal`, `timeout`, `no_plan`) without altering any control flow or mathematical formulation.
- `LinearBatteryStateMachine.calculate_next_state`: set `controller.time_budget_s` (clamped 1–60, default 30.0) and `controller.guard_target_soc` (default 100.0) from `context.config`; attach `solver_stats` to every `FSMResult`.
- `FSMResult.solver_stats: dict[str, Any] | None = None` in `fsm/base.py`.

### 2. Amber Spike Pre-Charge 80% by 16:00 (`rates.py`, `renewables_guard.py`, `coordinator.py`, `const.py`)
- `const.py`: `DEFAULT_GUARD_DAYTIME_DEADLINE = "16:00"`.
- `rates.py`: in both `_parse_entity` and `_parse_amber_express_entity` (and `update()` merge), include `"spike": interval.get("spike_status") in ("potential_spike", "spike") or interval.get("descriptor") == "spike"`.
- `renewables_guard.py`:
  - Check `any(r.get("spike") for r in rates[:144])`. If true, set `self.spike_triggered = True`, append `"Amber Spike Forecast"` to `self.trigger_reasons`, and activate `self.is_active = True` regardless of `trigger_mode` (`AND`/`OR`).
  - Set `self.target_soc = 80.0` when `self.spike_triggered and not low_energy_triggered` else `100.0`.
- `coordinator.py`:
  - When `guard_active`: if `self.renewables_guard.spike_triggered and not self.renewables_guard.low_energy_triggered`, resolve only `[daytime_deadline]` (default `"16:00"`, omitting `"05:00"`) and pass `"guard_target_soc": 80.0` in `fsm_context.config`. Otherwise preserve both deadlines and `100.0`.

### 3. Config (`const.py`, `config_flow.py`, `strings.json`, `translations/en.json`)
- `CONF_SOLVER_TIME_BUDGET = "solver_time_budget"`, `DEFAULT_SOLVER_TIME_BUDGET = 30.0`.
- NumberSelector (1–60, step 1, box) in both the initial `energy` step and the options `energy` step, after `export_margin`.
- Labels and descriptions in config and options sections of both JSON files, plus labels for `reserve_soc`, `round_trip_efficiency`, `export_margin`, and `entity.sensor.hbc_solve_time.name`.

### 4. Coordinator & Sensor (`coordinator.py`, `sensor.py`)
- Pass `"solver_time_budget"` into `fsm_context.config`.
- Maintain `self._solve_history` deque (24 h prune) → `solve_seconds_max_24h`.
- Add `solver_stats` and `solve_seconds_max_24h` to returned `data`, `solver_snapshot.result`, and `_build_telemetry_payload` (along with `last_update`, `observation_mode`, `no_import_periods`, `renewables_guard_active`, `renewables_avg`, `guard_triggers`).
- FR-18 warning log when `solve_seconds >= 0.8 * budget` or outcome != `optimal`.
- `HBCSolveTimeSensor` in `sensor.py`.

### 5. Dashboard (`frontend/hbc-dashboard.js`, `__init__.py`)
- Solver card under the status card showing Last solve, Budget, Passes, Max 24 h, and colour-coded outcome chip (`OPTIMAL` green/amber, `TIMEOUT`/`NO PLAN` red).
- Constraints bar badge on `timeout` or `no_plan`.
- Footer shows `"Plan last ran: <time> · solved in X.XX s"`.
- Bump panel `module_url` cache-buster `?v=56` → `?v=57` in `__init__.py`.
