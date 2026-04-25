# Tasks: Telemetry API Split

**Input**: Design documents from `/specs/050-telemetry-api-split/`
**Prerequisites**: plan.md, spec.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create `tasks.md` from plan and spec (Completed)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [x] T002 Implement `_build_telemetry_payload()` in `custom_components/house_battery_control/coordinator.py`
- [x] T003 Implement `_build_plan_matrix()` in `custom_components/house_battery_control/diagnostics.py`
- [x] T004 Implement `HBCApiTelemetryView` in `custom_components/house_battery_control/web.py`
- [x] T005 Implement `HBCApiPlanView` in `custom_components/house_battery_control/web.py`
- [x] T006 Implement `HBCApiOutlookView` in `custom_components/house_battery_control/web.py`
- [x] T007 Register new views and debug panel in `custom_components/house_battery_control/__init__.py`

---

## Phase 3: User Story 1 - Low Bandwidth Dashboard Viewing (Priority: P1) 🎯 MVP

**Goal**: Deliver a lightweight background polling mechanism to stop data overages.

**Independent Test**: Verify `/hbc/api/telemetry` is < 5KB and new frontend polls it.

### Tests for User Story 1
- [x] T008 [P] [US1] Add test for `/hbc/api/telemetry` response size and content in `tests/test_web.py`

### Implementation for User Story 1
- [x] T009 [US1] Create new root component `hbc-panel-lite.js` in `custom_components/house_battery_control/frontend/hbc-panel-lite.js`
- [x] T010 [US1] Implement `_fetchData()` in `hbc-panel-lite.js` to poll `/hbc/api/telemetry`
- [x] T011 [US1] Add inconspicuous debug link to `/hbc-debug` in `hbc-panel-lite.js`

---

## Phase 4: User Story 2 - Viewing the 30-Minute Plan Array (Priority: P2)

**Goal**: Deliver a columnar 30-min plan matrix to the frontend, saving 6x size.

**Independent Test**: Verify `/hbc/api/plan` returns a matrix and frontend renders it.

### Tests for User Story 2
- [x] T012 [P] [US2] Add test for `/hbc/api/plan` returning 30-min matrix format in `tests/test_web.py`

### Implementation for User Story 2
- [x] T013 [US2] Create lightweight plan table component `hbc-plan-table-lite.js`
- [x] T014 [US2] Implement parsing of columnar arrays in `hbc-plan-table-lite.js`
- [x] T015 [US2] Implement dynamic 5-min lazy loading in `hbc-plan-table-lite.js` when "5 Min" toggle is clicked.
- [x] T016 [US2] Create lightweight outlook component `hbc-outlook-lite.js` with explicit "Load Outlook" button.
- [x] T017 [US2] Implement fetch to `/hbc/api/outlook` when button is clicked in `hbc-outlook-lite.js`.

---

## Phase 5: User Story 3 - Debugging the Full Payload (Priority: P3)

**Goal**: Keep the legacy endpoint fully functional for debug.

**Independent Test**: Verify legacy `/hbc/api/status` is untouched and `/hbc-debug` works.

### Implementation for User Story 3
- [x] T018 [US3] Ensure `hbc-panel.js` and `hbc-plan-table.js` remain completely untouched to support the `/hbc-debug` panel registered in `__init__.py`.

---

### Phase N: Testing and Validation
- [x] T019 Run automated tests (`pytest tests/ -v`)
- [x] T020 Run static checks (`ruff check custom_components/ tests/`)
- [x] T021 Validate manual frontend behavior inside Home Assistant
