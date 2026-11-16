# Tasks: Plan Table Cost & Tariff Color Coding and Export Cost Accounting Fixes

**Input**: Design documents from `/specs/065-plan-cost-colors-and-sign/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `system_requirements.md`

## Phase 1: Setup & Specification

- [x] T001 Create feature branch `065-plan-cost-colors-and-sign` and author `specs/065-plan-cost-colors-and-sign/spec.md`
- [x] T002 Validate specification quality in `specs/065-plan-cost-colors-and-sign/checklists/requirements.md`
- [x] T003 Update `system_requirements.md` (§2.2.2) with Plan Table semantic color coding and bill-impact cost accounting requirements
- [x] T004 Author technical design and research in `specs/065-plan-cost-colors-and-sign/research.md` and `specs/065-plan-cost-colors-and-sign/plan.md`

---

## Phase 2: User Story 1 - Semantic Color Coding for Plan Costs & Tariffs (Priority: P1) 🎯 MVP

**Goal**: Color-code `Cost`, `Export`, and `Import` cells (`val-credit` green, `val-cost` red/coral, `val-neutral` muted) with header tooltips and footer legend in both `<hbc-plan-table-lite>` and `<hbc-plan-table>` across `5min` and `30min` resolutions, and bump panel cache-bust to `?v=58`.

**Independent Test**: Render `<hbc-plan-table-lite>` and `<hbc-plan-table>` with positive/negative/zero `Interval Cost`, negative/positive `Export Rate`, and negative/positive `Import Rate` rows and verify semantic classes, tooltips, legend, and `?v=58` registration.

### Tests for User Story 1 (TDD RED)

- [x] T005 [P] [US1] Add semantic color-coding, tooltip, and legend tests (both `5min` and `30min`) in `tests/js/hbc-plan-table.test.js`
- [x] T006 [P] [US1] Create `tests/js/hbc-plan-table-lite.test.js` testing `<hbc-plan-table-lite>` semantic color classes (`val-credit`, `val-cost`, `val-neutral`) across `Cost`, `Export`, and `Import` columns
- [x] T007 [P] [US1] Update panel cache-bust assertion to `?v=58` in `tests/test_init.py`

### Implementation for User Story 1 (TDD GREEN)

- [x] T008 [P] [US1] Implement `_cellClass`, header `title` tooltips, `.val-credit` / `.val-cost` / `.val-neutral` styles, and sign legend in `custom_components/house_battery_control/frontend/hbc-plan-table-lite.js`
- [x] T009 [P] [US1] Implement `_cellClass`, header `title` tooltips, `.val-credit` / `.val-cost` / `.val-neutral` styles, and sign legend in `custom_components/house_battery_control/frontend/hbc-plan-table.js`
- [x] T010 [US1] Increment panel `module_url` query strings to `?v=58` in `custom_components/house_battery_control/__init__.py`

---

## Phase 3: User Story 2 - Accurate `:25` / `:55` Settlement Interval Cost Display (Priority: P1)

**Goal**: Eliminate the 20% `Interval Cost` truncation on `299s` (`:25:01–:30:00` / `:55:01–:00:00`) Amber boundary intervals and ensure `30min` matrix summation preserves negative signs regardless of `$` placement.

**Independent Test**: Verify a `299s` export interval in `build_diagnostic_plan_table` computes a full 5-minute cost (`-$0.2045` vs truncated `-$0.1636`) and `_build_plan_matrix(resolution="30min")` preserves negative summed costs.

### Tests for User Story 2 (TDD RED)

- [x] T011 [US2] Add `299s` `:25` boundary interval cost test and `30min` negative cost aggregation test in `tests/test_web.py`

### Implementation for User Story 2 (TDD GREEN)

- [x] T012 [US2] Round `duration_mins` (`round((end - start).total_seconds() / 60.0)`) in `custom_components/house_battery_control/diagnostics.py`
- [x] T013 [US2] Strip `"$"` before numeric regex parsing in `_build_plan_matrix` in `custom_components/house_battery_control/coordinator.py`

---

## Phase 4: User Story 3 - Accurate Live Cumulative Cost Sign for Grid Exports (Priority: P1)

**Goal**: Align `TelemetryCostTracker._on_tick` with the LP solver cost formula `(import_delta * current_price_imp) - (export_delta * current_price_exp)` so positive feed-in exports reduce cumulative cost and negative feed-in exports increase cumulative cost.

**Independent Test**: Verify `TelemetryCostTracker._on_tick` subtracts export earnings when `current_price_exp > 0` and adds export penalty cost when `current_price_exp < 0`.

### Tests for User Story 3 (TDD RED)

- [x] T014 [US3] Update positive feed-in test and add negative feed-in solar-sponge penalty test in `tests/test_telemetry_tracker.py`

### Implementation for User Story 3 (TDD GREEN)

- [x] T015 [US3] Fix export delta sign to `- (export_delta * current_price_exp)` in `custom_components/house_battery_control/telemetry_tracker.py`

---

## Phase 5: Polish & Cross-Cutting Verification

- [x] T016 Run full Python test suite (`pytest tests/ -q`), JS unit tests (`npm test`), Python linter (`ruff check custom_components/ tests/`), JS linter (`npm run lint:js`), and verify zero diff on `custom_components/house_battery_control/fsm/lin_fsm.py`
- [x] T017 Record verification results in `specs/065-plan-cost-colors-and-sign/validation.md`

## Dependencies & Execution Order

- **Phase 1 (Setup & Spec)**: Complete (`T001`–`T004`). Blocks all code changes until user approves plan.
- **User Stories 1, 2, 3 (Phases 2–4)**: Complete (`T005`–`T015`).
- **Phase 5 (Verification)**: Full `pytest` suite running.
