# Tasks: Negative-tariff calculations

Approved scope: calculation only for Phases 1–6; non-destructive solver visibility (US4) and Amber spike 80%-by-16:00 pre-charge (US5) in Phases 7–10. SDD/TDD required by user.

## Phase 1 — Setup

- [x] T001 Record approval and calculation-only scope in specs/063-negative-tariff-dispatch/spec.md and plan.md.
- [x] T002 Run local Spec Kit prerequisite checks and trace solver consumers; record blast radius in specs/063-negative-tariff-dispatch/validation.md.
- [x] T003 Establish existing solver-test baseline and record results in specs/063-negative-tariff-dispatch/validation.md.

## Phase 2 — Foundation

- [x] T004 Write permanent failing regression tests for exact balances and tariff policy against the existing controller in tests/test_negative_tariffs.py; capture RED before production edits.
- [x] T005 Record in-place compatibility boundary and compatibility contract in docs/architecture.md before implementing custom_components/house_battery_control/fsm/lin_fsm.py.

## Phase 3 — US1 (P1): Physically valid flows and no negative battery export

- [x] T006 [US1] Implement exact sparse MILP, direction constraints, input checks and independent solution validation in custom_components/house_battery_control/fsm/lin_fsm.py after T004 is RED.
- [x] T007 [US1] Run tests/test_negative_tariffs.py physical/policy cases against the corrected controller, record GREEN and check positive-price/export-margin compatibility.

## Phase 4 — US2 (P1): Paid charging includes future solar-export cost

- [x] T008 [US2] Add and run failing hand-calculated candidate/reference, tie and loss tests in tests/test_negative_tariffs.py before comparison implementation.
- [x] T009 [US2] Implement same-horizon candidate/reference economics, truthful cash/terminal diagnostics and tie preference in custom_components/house_battery_control/fsm/lin_fsm.py.
- [x] T010 [US2] Run economic regressions, reconcile cash independently and record GREEN in specs/063-negative-tariff-dispatch/validation.md.

## Phase 5 — US3 (P1): Consistent calculation output and safe fallback

- [x] T011 [US3] Write and run adapter, malformed result, reserve, deadline and timeout regressions; record missing-behaviour failures in tests/test_negative_tariffs.py before implementing the adapter.
- [x] T012 [US3] Implement FSM-compatible adapter and trajectory-derived accounting in custom_components/house_battery_control/fsm/lin_fsm.py; preserve existing mode command interface.
- [x] T013 [US3] Verify unchanged calculation imports in custom_components/house_battery_control/coordinator.py and preserve the existing controller/FSM signatures in custom_components/house_battery_control/fsm/lin_fsm.py.
- [x] T014 [US3] Verify offline tests/test_fsm_lin.py and tests/test_solver_replay.py; check unchanged imports and verify execute.py has no diff. HA integration tests excluded by user direction.

## Phase 6 — Cross-cutting verification

- [x] T015 Verify finite/equal-length/nonnegative solver inputs in tests/test_negative_tariffs.py; document that source staleness and padded-forecast provenance remain outside the calculation-only boundary; make no metadata/API changes.
- [x] T016 Run focused regressions and representative 288/576-step benchmarks; record failures and timings in specs/063-negative-tariff-dispatch/validation.md.
- [x] T017 Reconcile approved scope, architecture, completed tasks and remaining deployment limitations in specs/063-negative-tariff-dispatch/plan.md and docs/architecture.md.

---

# Amendment — US4 (Non-destructive solve-time budget & visibility) and US5 (Amber spike pre-charge 80% by 16:00)

## Phase 7 — US4 & US5 baseline

- [x] T018 [US4] Record pre-change baseline (`pytest tests/ -q`, `ruff check custom_components/ tests/`, `npm run lint:js`) in specs/063-negative-tariff-dispatch/validation.md.

## Phase 8 — US4 & US5 tests first (RED)

- [x] T019 [P] [US4] Create tests/test_solver_budget.py: (a) snapshot invariance check proving `propose_state_of_charge` output is identical under default settings; (b) `last_solve_stats` has all SolverStats keys (`optimal`, `passes >= 1`, `budget_seconds == 30.0`); (c) `time_budget_s` honoured; (d) patched `monotonic` exhausting budget → empty plan with `outcome == "timeout"`; (e) invalid inputs → `outcome == "no_plan"`, `passes == 0`; (f) `guard_target_soc = 80.0` caps deadline bound at 80% of capacity.
- [x] T020 [P] [US4] Add adapter tests in tests/test_solver_budget.py: `LinearBatteryStateMachine.calculate_next_state` clamps `solver_time_budget` to [1, 60] (default 30.0), forwards `guard_target_soc`, and populates `FSMResult.solver_stats` on all paths.
- [x] T021 [P] [US5] Add spike parsing & guard tests in tests/test_rates.py and tests/test_renewables_guard.py: `_parse_entity` and `_parse_amber_express_entity` set `spike=True` on `spike_status in ("potential_spike", "spike")` or `descriptor == "spike"`; `RenewablesGuard.evaluate` triggers on `spike=True` in next 12h even in `"AND"` mode with high renewables/solar, setting `spike_triggered=True` and `target_soc=80.0`; `DEFAULT_GUARD_DAYTIME_DEADLINE == "16:00"`.
- [x] T022 [P] [US4] Add coordinator & telemetry tests in tests/test_coordinator.py: `solver_time_budget` and spike-only `guard_target_soc=80.0` (with only daytime deadline resolved) reach `fsm_context`; returned data and `_build_telemetry_payload` contain `solver_stats`, `solve_seconds_max_24h`, `last_update`, `observation_mode`, `no_import_periods`, `renewables_guard_active`, `renewables_avg`, `guard_triggers`; FR-18 warning logged on slow/non-optimal solve.
- [x] T023 [P] [US4] Add sensor tests in tests/test_sensor.py: `HBCSolveTimeSensor` (`hbc_solve_time`, DURATION, seconds, MEASUREMENT, DIAGNOSTIC, attributes, registered in `async_setup_entry`).
- [x] T024 [P] [US4] Add config & translation tests in tests/test_config_flow.py: `solver_time_budget` in both energy steps (default 30.0, min 1, max 60); labels/descriptions in `strings.json` and `translations/en.json` (plus `reserve_soc`, `round_trip_efficiency`, `export_margin`, and `entity.sensor.hbc_solve_time.name`).
- [x] T025 [P] [US4] Add front-end & panel tests in tests/js/hbc-dashboard.test.js and tests/test_init.py: dashboard renders Solver card, outcome chip, fallback/timeout badge, and footer solve time; `__init__.py` registers panels with `?v=57`.
- [x] T026 [US4] Run T019–T025 and record RED evidence in specs/063-negative-tariff-dispatch/validation.md.

## Phase 9 — US4 & US5 implementation (GREEN)

- [x] T027 [US4] Add optional `solver_stats: dict[str, Any] | None = None` to `FSMResult` in custom_components/house_battery_control/fsm/base.py.
- [x] T028 [US4] [US5] Update custom_components/house_battery_control/fsm/lin_fsm.py non-destructively: add `time_budget_s = 30.0`, `guard_target_soc = 100.0`, `last_solve_stats`, read-only counters, and adapter pass-through.
- [x] T029 [P] [US5] Update custom_components/house_battery_control/rates.py and custom_components/house_battery_control/renewables_guard.py for spike detection (`spike` flag, `spike_triggered`, `target_soc = 80.0`).
- [x] T030 [P] [US4] [US5] Update custom_components/house_battery_control/const.py (`CONF_SOLVER_TIME_BUDGET`, `DEFAULT_SOLVER_TIME_BUDGET = 30.0`, `DEFAULT_GUARD_DAYTIME_DEADLINE = "16:00"`) and custom_components/house_battery_control/config_flow.py.
- [x] T031 [P] [US4] Update custom_components/house_battery_control/strings.json and custom_components/house_battery_control/translations/en.json.
- [x] T032 [US4] [US5] Update custom_components/house_battery_control/coordinator.py (spike-only daytime deadline + `guard_target_soc=80.0`, `solver_time_budget`, `solver_stats`, `solve_seconds_max_24h`, FR-18 warning, `_build_telemetry_payload`).
- [x] T033 [P] [US4] Add `HBCSolveTimeSensor` in custom_components/house_battery_control/sensor.py.
- [x] T034 [US4] Update custom_components/house_battery_control/frontend/hbc-dashboard.js and bump `?v=57` in custom_components/house_battery_control/__init__.py.
- [x] T035 [US4] [US5] Run T019–T025 to GREEN and verify `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is strictly non-destructive.

## Phase 10 — Verification

- [x] T036 Run full `pytest tests/ -q`, `ruff check custom_components/ tests/`, and `npm run lint:js`; record results in specs/063-negative-tariff-dispatch/validation.md.
