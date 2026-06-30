# Tasks: Solar Today Guard Trigger (056)

**Feature**: 056-solar-today-guard  
**Branch**: `056-solar-today-guard`  
**Spec**: [spec.md](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/specs/056-solar-today-guard/spec.md)  
**Plan**: [plan.md](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/specs/056-solar-today-guard/plan.md)

---

## Phase 1: Guard Logic — Add Solcast Today Trigger (Priority: P1)

- [x] T001 Write test `test_guard_today_solar_triggers_alone`
- [x] T002 Write test `test_guard_today_solar_high_no_trigger`
- [x] T003 Write test `test_guard_and_mode_all_three_required`
- [x] T004 Write test `test_guard_and_mode_today_high_blocks`
- [x] T005 Write test `test_guard_or_mode_today_only`
- [x] T006 Add `solcast_today: float` parameter to `evaluate()`
- [x] T007 Add Solcast today evaluation logic (same threshold as tomorrow)
- [x] T008 Update trigger mode: OR = any of 3; AND = all 3
- [x] T009 Update existing `test_guard_and_mode_both_fire` to include `solcast_today`
- [x] T010 Regression: 20/20 guard tests pass

## Phase 2: Coordinator Wiring (Priority: P1)

- [x] T011 Write test `test_coordinator_guard_today_solar_trigger`
- [x] T012 Read `solcast_today` from `CONF_SOLCAST_TODAY_ENTITY` in coordinator
- [x] T013 Pass `solcast_today=solcast_today` to `evaluate()`
- [x] T014 Existing coordinator guard tests pass (backward-compatible default)
- [x] T015 Regression: 37/37 coordinator tests pass
- [x] T016 Full suite: 301 passed, 2 xfailed, 0 failures

## Phase 3: Final Validation

- [x] T017 Lint: `ruff check` — All checks passed
- [x] T018 Full suite: 301 passed, 0 failures
- [ ] T019 Update spec.md status from "Draft" to "Implemented"
- [ ] T020 Commit and push, create release
