# Tasks: 039-frontend-testing

**Input**: Design documents from `/specs/039-frontend-testing/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Initialize Node package environment by creating `package.json` in the root repository.
- [x] T002 Add a `"test": "web-test-runner"` script definition to `package.json`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create the Web Test Runner configuration file `web-test-runner.config.js` to serve the `custom_components` directory and run tests in a headless browser.
- [x] T004 [P] Create the `tests/js/` directory to house the upcoming unit tests.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Formalize System Requirements Artifact (Priority: P1) 🎯 MVP

**Goal**: Update the central `system_requirements.md` to be formally recognized as a persistent, living artifact, mapping the frontend logic.

**Independent Test**: Can be verified by updating the `system_requirements.md` with the new frontend requirements and observing that the project documentation accurately reflects the current state of the application.

### Implementation for User Story 1

- [x] T005 [US1] Update `system_requirements.md` (Section 2.2) to formally document the required behavior and structure of the `<hbc-dashboard>` component.
- [x] T006 [US1] Update `system_requirements.md` (Section 2.2) to formally document the `localStorage` and rendering behavior of the `<hbc-sensors>` component.
- [x] T007 [US1] Update `system_requirements.md` (Section 2.2) to formally document the 30-minute chunking math and `localStorage` behavior of the `<hbc-plan-table>` component.
- [x] T008 [US1] Append a note to `system_requirements.md` establishing the mandatory rule that every new feature must update this specification document.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Establish JavaScript Testing Framework (Priority: P2)

**Goal**: Install and configure the JavaScript testing framework dependencies for TDD.

**Independent Test**: Can be verified by running `npm test` and seeing successful execution of the test suite (even if empty).

### Implementation for User Story 2

- [x] T009 [P] [US2] Install dev dependencies `@web/test-runner` and `@open-wc/testing` via `npm install --save-dev` in the root repository.
- [x] T010 [US2] Create a dummy test file in `tests/js/dummy.test.js` to test the environment runner.
- [x] T011 [US2] Execute `npm test` to verify the headless browser launches successfully and passes the dummy test.
- [x] T012 [US2] Remove the `tests/js/dummy.test.js` file now that the infrastructure is validated.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Implement Web Component Tests (Priority: P3)

**Goal**: Write comprehensive unit tests for the three LitElement components.

**Independent Test**: Can be fully tested by running `npm test` and observing a 100% pass rate for the specific component tests.

### Tests for User Story 3 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (or pass if the existing code is already correct).**

- [x] T013 [P] [US3] Create unit tests for `hbc-dashboard` in `tests/js/hbc-dashboard.test.js` (validating summary math and rendering).
- [x] T014 [P] [US3] Create unit tests for `hbc-sensors` in `tests/js/hbc-sensors.test.js` (validating visibility toggling and `localStorage`).
- [x] T015 [P] [US3] Create unit tests for `hbc-plan-table` in `tests/js/hbc-plan-table.test.js` (validating 30-min chunk averaging, boundary states, and `localStorage`).

### Implementation for User Story 3

- [x] T016 [US3] Run the full `npm test` suite. If any tests fail against the *existing* components, refactor the test (or the component) until the suite achieves a 100% pass rate.

**Checkpoint**: All user stories should now be independently functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T017 Code cleanup and `package-lock.json` review.
- [x] T018 Run quickstart.md validation locally to ensure instructions are accurate.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P3)**: Depends heavily on **User Story 2** since it requires the testing framework to be installed and operational before running the unit tests.

### Within Each User Story

- Tests MUST be written and run before integration is considered complete.
- Core implementation before integration.

### Parallel Opportunities

- Documentation tasks in US1 (T005, T006, T007) can be done in parallel.
- Test suite creation in US3 (T013, T014, T015) can be authored in parallel by multiple developers.

---

## Parallel Example: User Story 3

```bash
# Launch all test creation tasks for User Story 3 together:
Task: "Create unit tests for hbc-dashboard in tests/js/hbc-dashboard.test.js"
Task: "Create unit tests for hbc-sensors in tests/js/hbc-sensors.test.js"
Task: "Create unit tests for hbc-plan-table in tests/js/hbc-plan-table.test.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Validate testing architecture
4. Add User Story 3 → Test independently → Achieve 100% frontend test coverage.
5. Each story adds value without breaking previous stories.
