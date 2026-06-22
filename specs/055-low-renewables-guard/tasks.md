# Tasks: Low Renewables Guard (055)

**Input**: Design documents from `/specs/055-low-renewables-guard/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅
**Tests**: TDD — all tests written FIRST and must FAIL before implementation code.

**Organization**: Tasks grouped by user story. SDD→TDD execution: tests RED → implementation GREEN → refactor.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup

**Purpose**: New module scaffolding and config constants

- [ ] T001 Add guard config constants to `custom_components/house_battery_control/const.py` — CONF_GUARD_RENEWABLES_THRESHOLD, CONF_GUARD_OVERNIGHT_DEADLINE, CONF_GUARD_DAYTIME_DEADLINE, CONF_GUARD_PEAK_SOLAR, CONF_GUARD_TRIGGER_MODE, CONF_GUARD_LOW_SOLAR_THRESHOLD and their DEFAULT_ values
- [ ] T002 [P] Add `guard_deadline_steps: list[int] | None = None` field to `SolverInputs` dataclass in `custom_components/house_battery_control/fsm/base.py`
- [ ] T003 [P] Add `renewables: float | None` field to `RateInterval` TypedDict in `custom_components/house_battery_control/rates.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Preserve renewables % in the rates pipeline — required before guard detection can work

**⚠️ CRITICAL**: No user story work can begin until renewables data flows through the pipeline

### Tests (write FIRST — must FAIL)

- [ ] T004 [P] Write test `test_amber_express_preserves_renewables` in `tests/test_rates.py` — verify parsed Amber Express intervals include `renewables` field with correct value
- [ ] T005 [P] Write test `test_amber_express_renewables_default` in `tests/test_rates.py` — verify missing `renewables` field defaults to `None`
- [ ] T006 [P] Write test `test_standard_amber_renewables_none` in `tests/test_rates.py` — verify non-Express intervals have `renewables: None`

### Implementation (make tests GREEN)

- [ ] T007 Modify `_parse_amber_express_entity()` in `custom_components/house_battery_control/rates.py` to include `renewables` in parsed output dict (L186-193)
- [ ] T008 Modify `_parse_amber_entity()` in `custom_components/house_battery_control/rates.py` to include `renewables: None` in parsed output dict
- [ ] T009 Modify `_merge_import_export()` in `custom_components/house_battery_control/rates.py` to carry `renewables` field from import intervals into merged `RateInterval`
- [ ] T010 Run `pytest tests/test_rates.py -v -k "renewables"` — all 3 tests must pass. Then run full `pytest tests/test_rates.py -v` — zero regressions.

**Checkpoint**: Renewables % now flows through the full rates pipeline.

---

## Phase 3: User Story 1 — Automatic Low Renewables Detection (Priority: P1)

**Goal**: Detect low renewables from Amber Express forecast, activate/deactivate guard with hysteresis, OR/AND trigger mode

**Independent Test**: Inject mock renewables timelines and verify guard activates at ≤30%, stays active at 35% (hysteresis), deactivates at 42%

### Tests (write FIRST — must FAIL)

- [ ] T011 [P] [US1] Write test `test_guard_activates_below_threshold` in `tests/test_renewables_guard.py` — avg renewables 4.9% → guard active, triggers=["renewables"]
- [ ] T012 [P] [US1] Write test `test_guard_inactive_above_threshold` in `tests/test_renewables_guard.py` — avg renewables 65% → guard inactive
- [ ] T013 [P] [US1] Write test `test_guard_hysteresis_no_deactivate_at_35` in `tests/test_renewables_guard.py` — guard active, next cycle renewables 35% → stays active
- [ ] T014 [P] [US1] Write test `test_guard_deactivates_above_40` in `tests/test_renewables_guard.py` — guard active, next cycle renewables 42% → deactivates
- [ ] T015 [P] [US1] Write test `test_guard_no_amber_express_data` in `tests/test_renewables_guard.py` — None renewables timeline → guard inactive (fail-safe)
- [ ] T016 [P] [US1] Write test `test_guard_empty_renewables` in `tests/test_renewables_guard.py` — empty list → guard inactive
- [ ] T017 [P] [US1] Write test `test_guard_partial_forecast_data` in `tests/test_renewables_guard.py` — fewer than 12h of forecast intervals available → averages across all available intervals and evaluates correctly
- [ ] T018 [P] [US1] Write test `test_guard_or_mode_renewables_only` in `tests/test_renewables_guard.py` — low renewables + high solar → active (OR mode)
- [ ] T019 [P] [US1] Write test `test_guard_or_mode_solar_only` in `tests/test_renewables_guard.py` — high renewables + low solar → active (OR mode)
- [ ] T020 [P] [US1] Write test `test_guard_and_mode_both_required` in `tests/test_renewables_guard.py` — low renewables + high solar → inactive (AND mode)
- [ ] T021 [P] [US1] Write test `test_guard_and_mode_both_fire` in `tests/test_renewables_guard.py` — low renewables + low solar → active (AND mode)

### Implementation (make tests GREEN)

- [ ] T022 [US1] Create `RenewablesGuard` class with `evaluate()` method in `custom_components/house_battery_control/renewables_guard.py` — implements GuardState dataclass, hysteresis logic (activate ≤30%, deactivate >40%), OR/AND trigger mode, 12h average calculation (uses all available intervals if <12h)
- [ ] T023 [US1] Run `pytest tests/test_renewables_guard.py -v` — all 11 tests must pass

**Checkpoint**: Guard logic works in isolation. No HA dependencies.

---

## Phase 4: User Story 2 + 3 — SoC Deadlines (Priority: P1+P2)

**Goal**: When guard active, solver targets 100% SoC by 05:00 (overnight) and 15:00 (daytime), applied to both today and tomorrow when 48h data available

**Independent Test**: Run LP solver with guard_deadline_steps and verify battery state reaches capacity at each deadline step index

### Tests (write FIRST — must FAIL)

- [ ] T024 [P] [US2] Write test `test_resolve_deadlines_today_only` in `tests/test_renewables_guard.py` — 24h rates timeline → correctly finds step indices for 05:00 and 15:00
- [ ] T025 [P] [US2] Write test `test_resolve_deadlines_48h` in `tests/test_renewables_guard.py` — 48h rates timeline → finds 4 step indices (today 05:00+15:00, tomorrow 05:00+15:00)
- [ ] T026 [P] [US2] Write test `test_resolve_deadlines_past_deadline` in `tests/test_renewables_guard.py` — current time is 08:00, only tomorrow's 05:00 is resolved (today's 05:00 has passed)
- [ ] T027 [P] [US3] Write test `test_resolve_deadlines_custom_times` in `tests/test_renewables_guard.py` — deadline at 04:00 and 14:00 → correct step indices
- [ ] T028 [P] [US2] Write test `test_guard_deadline_raises_battery_lower_bound` in `tests/test_fsm_lin.py` — pass guard_deadline_steps=[60], verify `b[60]` lower bound equals capacity
- [ ] T029 [P] [US2] Write test `test_guard_deadline_solver_charges_cheapest` in `tests/test_fsm_lin.py` — cheap overnight prices with deadline at step 60, verify plan shows CHARGE_GRID during cheap intervals
- [ ] T030 [P] [US2] Write test `test_guard_deadline_no_effect_when_none` in `tests/test_fsm_lin.py` — guard_deadline_steps=None → normal bounds unchanged
- [ ] T031 [P] [US2] Write test `test_guard_deadline_already_full` in `tests/test_fsm_lin.py` — battery at 100% SoC → solver doesn't over-charge (already satisfied)
- [ ] T032 [P] [US2] Write test `test_guard_deadline_coexists_with_no_import` in `tests/test_fsm_lin.py` — both no_import_steps and guard_deadline_steps active simultaneously, verify no conflict
- [ ] T033 [P] [US2] Write test `test_guard_active_export_still_permitted` in `tests/test_fsm_lin.py` — guard active with deadline, export price is high, verify solver still chooses DISCHARGE_GRID when profitable (FR-007)
- [ ] T034 [P] [US3] Write test `test_guard_daytime_deadline_with_solar` in `tests/test_fsm_lin.py` — guard active, PV generating 2kW, deadline at step 180 (15:00), verify plan favours solar capture + charging toward deadline
- [ ] T035 [P] [US3] Write test `test_guard_daytime_deadline_no_solar` in `tests/test_fsm_lin.py` — guard active, PV=0, deadline at step 180, verify plan charges from grid at cheapest intervals

### Implementation (make tests GREEN)

- [ ] T036 [US2] Add `resolve_deadline_steps()` method to `RenewablesGuard` in `custom_components/house_battery_control/renewables_guard.py` — iterate rates timeline, convert UTC→local time, match deadline hours, return step indices for today + tomorrow
- [ ] T037 [US2] Modify `propose_state_of_charge()` in `custom_components/house_battery_control/fsm/lin_fsm.py` to accept `guard_deadline_steps` parameter and raise `bounds[b_off + i]` lower bound to `capacity` for deadline steps (L192-200)
- [ ] T038 [US2] Modify `calculate_next_state()` in `custom_components/house_battery_control/fsm/lin_fsm.py` to extract `si.guard_deadline_steps` and pass to `propose_state_of_charge()`
- [ ] T039 Run `pytest tests/test_renewables_guard.py tests/test_fsm_lin.py -v -k "deadline or guard"` — all tests must pass. Then full `pytest tests/test_fsm_lin.py -v` — zero regressions.

**Checkpoint**: Solver correctly targets 100% SoC at both 05:00 and 15:00 deadline steps, including 48h horizon.

---

## Phase 5: User Story 4 — Configuration Controls (Priority: P2)

**Goal**: Guard settings configurable via HA options flow

**Independent Test**: Change guard settings in options flow and verify values stored correctly

### Tests (write FIRST — must FAIL)

- [ ] T040 [P] [US4] Write test `test_config_flow_guard_fields_present` in `tests/test_config_flow.py` — verify control step schema includes guard fields with correct defaults
- [ ] T041 [P] [US4] Write test `test_config_flow_guard_values_saved` in `tests/test_config_flow.py` — submit guard settings and verify they are stored in config entry data

### Implementation (make tests GREEN)

- [ ] T042 [US4] Add guard settings to `async_step_control()` in `custom_components/house_battery_control/config_flow.py` — renewables threshold (NumberSelector %), overnight deadline (TimeSelector), daytime deadline (TimeSelector), peak solar reference (NumberSelector kWh), trigger mode (SelectSelector OR/AND), low solar threshold (NumberSelector %)
- [ ] T043 [US4] Add UI strings for guard settings in `custom_components/house_battery_control/strings.json` and `custom_components/house_battery_control/translations/en.json`
- [ ] T044 [US4] Run `pytest tests/test_config_flow.py -v -k "guard"` — all tests must pass. Then full `pytest tests/test_config_flow.py -v` — zero regressions.

**Checkpoint**: Guard fully configurable from HA UI.

---

## Phase 6: Coordinator Integration (Orchestration)

**Purpose**: Wire the guard into the coordinator update cycle — connects all components

### Tests (write FIRST — must FAIL)

- [ ] T045 [P] Write test `test_coordinator_guard_active_with_low_renewables` in `tests/test_coordinator.py` — mock Amber Express data with 4.9% renewables, verify coordinator returns `renewables_guard_active: True`
- [ ] T046 [P] Write test `test_coordinator_guard_inactive_high_renewables` in `tests/test_coordinator.py` — mock 65% renewables, verify coordinator returns `renewables_guard_active: False`
- [ ] T047 [P] Write test `test_coordinator_guard_passes_deadlines_to_solver` in `tests/test_coordinator.py` — guard active, verify `SolverInputs.guard_deadline_steps` is populated with correct step indices
- [ ] T048 [P] Write test `test_coordinator_guard_skipped_without_amber_express` in `tests/test_coordinator.py` — standard Amber mode, verify guard silently skipped, no errors

### Implementation (make tests GREEN)

- [ ] T049 Instantiate `RenewablesGuard` in `custom_components/house_battery_control/coordinator.py` `__init__()` — persist across cycles for hysteresis state
- [ ] T050 In `_async_update_data()` in `custom_components/house_battery_control/coordinator.py`: after `self.rates.update()`, extract renewables timeline from parsed rates; read Solcast tomorrow forecast via `hass.states.get()`; call `guard.evaluate()`; if active, call `guard.resolve_deadline_steps()`
- [ ] T051 In `_build_solver_inputs()` in `custom_components/house_battery_control/coordinator.py`: accept and pass `guard_deadline_steps` to `SolverInputs(...)`
- [ ] T052 In return data dict (~L693) in `custom_components/house_battery_control/coordinator.py`: add `renewables_guard_active`, `renewables_avg`, `guard_triggers` keys
- [ ] T053 Run `pytest tests/test_coordinator.py -v -k "guard"` — all tests must pass. Then full `pytest tests/test_coordinator.py -v` — zero regressions.

**Checkpoint**: Full end-to-end guard → solver → plan pipeline working.

---

## Phase 7: User Story 5 — Dashboard Visibility (Priority: P3)

**Goal**: Guard status badge visible on dashboard when active

**Independent Test**: Activate the guard and verify the badge renders with renewables % and deadline info

### Tests (write FIRST — must FAIL)

- [ ] T054 [P] [US5] Write test for guard badge rendering in `tests/js/` — verify badge HTML appears when `renewables_guard_active: true`
- [ ] T055 [P] [US5] Write test for guard badge hidden when inactive — verify no badge HTML when `renewables_guard_active: false`

### Implementation (make tests GREEN)

- [ ] T056 [US5] Add guard data extraction in `custom_components/house_battery_control/frontend/hbc-dashboard.js` — read `renewables_guard_active`, `renewables_avg`, `guard_triggers` from coordinator data
- [ ] T057 [US5] Add guard badge `<span class="constraint-badge renewables">` to constraints-bar in `custom_components/house_battery_control/frontend/hbc-dashboard.js` — shows "⚡ Low Renewables: X% — Targets: 05:00, 15:00"
- [ ] T058 [US5] Add CSS for `.constraint-badge.renewables` in `custom_components/house_battery_control/frontend/hbc-dashboard.js` — amber/orange gradient matching existing badge style
- [ ] T059 [US5] Run JS tests if applicable; visually verify badge in browser

**Checkpoint**: Dashboard shows guard status when active, clean when inactive.

---

## Phase 8: Final Validation

**Purpose**: Full regression and completion

- [ ] T060 Run full test suite: `pytest tests/ -v` — zero regressions across ALL existing tests
- [ ] T061 Run all guard-specific tests: `pytest tests/test_renewables_guard.py tests/test_fsm_lin.py tests/test_rates.py tests/test_coordinator.py tests/test_config_flow.py -v` — all pass
- [ ] T062 Update spec.md status from "Draft" to "Implemented" in `specs/055-low-renewables-guard/spec.md`
- [ ] T063 Commit all changes and push branch `055-low-renewables-guard`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
  └─→ Phase 2 (Foundational: rates pipeline)
        └─→ Phase 3 (US1: detection logic)
              └─→ Phase 4 (US2+US3: solver deadlines)
                    ├─→ Phase 5 (US4: config flow) — can run parallel with Phase 4
                    └─→ Phase 6 (Coordinator: wiring)
                          └─→ Phase 7 (US5: dashboard)
                                └─→ Phase 8 (Final validation)
```

### Within Each Phase (TDD Order)

1. Write ALL tests for the phase → commit → verify they FAIL
2. Write implementation code → verify tests PASS
3. Run regression → verify no existing tests broke
4. Commit

### Parallel Opportunities

- T002, T003 alongside T001 (different files)
- T004-T006 all [P] (independent test functions)
- T011-T020 all [P] (independent test functions)
- T023-T033 all [P] (across two test files)
- Phase 5 (config flow) can overlap with Phase 4 (solver) — different files entirely
- T043-T046 all [P] (independent coordinator tests)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- All tests MUST be written and FAIL before implementation code
- Commit after each phase completion
- Existing test suite must pass at every checkpoint
- US2 and US3 are combined in Phase 4 — same mechanism (deadline resolution + solver bounds), different times
