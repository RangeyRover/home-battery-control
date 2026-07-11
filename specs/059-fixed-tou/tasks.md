# Tasks: Fixed TOU Support

**Input**: Design documents from `/specs/059-fixed-tou/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: The tasks below explicitly enforce the TDD mandate. The tests must be written and validated as failing BEFORE the core implementation tasks are executed.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic data model additions.

- [ ] T001 Create `CONF_PRICING_MODE` and `CONF_FIXED_TOU_*` constants in `custom_components/house_battery_control/const.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 Update translations file `custom_components/house_battery_control/translations/en.json` to include new Config Flow strings for Fixed TOU.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Configure Fixed TOU Tariffs (Priority: P1) 🎯 MVP

**Goal**: As a user with a fixed Time-of-Use electricity plan, I want to manually configure my Peak, Shoulder, and Off-Peak times and rates within the integration's Config Flow so that I don't have to build complex Home Assistant template sensors to mimic dynamic pricing.

**Independent Test**: Can be fully tested by configuring the integration with fixed TOU settings and verifying that the backend generates a valid 48-hour forecast array conforming to the expected Amber JSON schema.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T003 [P] [US1] Create Config Flow isolation tests (Pricing Mode switch) in `tests/test_config_flow.py`

### Implementation for User Story 1

- [ ] T004 [US1] Implement `async_step_pricing_mode` and update `async_step_energy` branching in `custom_components/house_battery_control/config_flow.py` (depends on T003)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Accurate Timezone and DST Handling (Priority: P1)

**Goal**: As a user in a region with Daylight Saving Time, I want the generated TOU schedule to accurately align with my local wall-clock time so that the battery optimally charges and discharges during the correct tariff periods even when the clocks change.

**Independent Test**: Can be tested by simulating a timezone with an upcoming DST shift (e.g., Sydney time around October/April) and verifying that the generated 48-hour forecast accurately maps the peak/off-peak windows across the time shift boundary.

### Tests for User Story 2 ⚠️

- [ ] T005 [P] [US2] Create unit tests for `FixedTOUGenerator` output and DST boundary mapping in `tests/test_fixed_tou.py`

### Implementation for User Story 2

- [ ] T006 [US2] Implement the `FixedTOUGenerator` class logic in `custom_components/house_battery_control/fixed_tou.py` (depends on T005)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Transparent Config Reloads (Priority: P2)

**Goal**: As a user updating my electricity contract, I want to change my Fixed TOU rates in the Config Flow and have the system begin using the new rates automatically after the integration reloads.

**Independent Test**: Can be tested by modifying the TOU rates in the integration's options flow and verifying that the solver immediately uses the new prices on the next tick post-reload.

### Tests for User Story 3 ⚠️

- [ ] T007 [P] [US3] Create integration tests for the `RatesManager` solver input switch in `tests/test_coordinator.py`

### Implementation for User Story 3

- [ ] T008 [US3] Update `RatesManager` initialization and fetch logic in `custom_components/house_battery_control/coordinator.py` to route to `FixedTOUGenerator` when in Fixed TOU mode.

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T009 Code cleanup and refactoring
- [ ] T010 Final end-to-end testing verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2)
- **User Story 2 (P1)**: Can start after Foundational (Phase 2)
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Requires US2's `FixedTOUGenerator` to be complete to function fully in production, but tests can be written independently.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD).
- Core implementation before integration.

### Parallel Opportunities

- T003, T005, and T007 can all be written concurrently since they target independent files/components.
- T004 and T006 can be developed concurrently after their respective tests are written.

---

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. Complete Phase 1 & 2: Setup & Foundation
2. Complete Phase 3: Config Flow UI (US1)
3. Complete Phase 4: Generator Logic (US2)
4. **STOP and VALIDATE**: Test User Story 1 & 2 independently
5. Complete Phase 5: Connect Generator to Solver (US3)
