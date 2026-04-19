# Tasks: Tomorrow's Outlook UI

**Input**: Design documents from `/specs/046-tomorrows-outlook-ui/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)

---

## Phase 1: Setup

**Purpose**: Project initialization and basic structure

- [x] T001 Verify `custom_components/house_battery_control/coordinator.py` correctly populates `self.data["synthetic_outlook"]` with the arrays.
- [x] T002 Verify `custom_components/house_battery_control/web.py` registers the new module `hbc-outlook.js` (handled via `__init__.py` static path).

---

## Phase 2: User Story 1 - Tomorrow's Outlook Tab (Priority: P1) 🎯 MVP

**Goal**: Users view a dedicated "Tomorrow's Outlook" tab in the House Battery Control UI.

### Implementation for User Story 1

- [x] T003 [US1] Create `custom_components/house_battery_control/frontend/hbc-outlook.js` with a basic LitElement scaffolding.
- [x] T004 [US1] Update `hbc-panel.js` to include the "Tomorrow's Outlook" tab in the navigation menu.
- [x] T005 [US1] Update `hbc-panel.js` to render `<hbc-outlook>` when the tab is active.
- [x] T006 [US1] Pass `hass` and `state` properties down to `<hbc-outlook>`.

---

## Phase 3: User Story 2 - Render Graphs and Analog Sources (Priority: P2)

**Goal**: Visualize the three core curves and the 5 analog dates.

### Implementation for User Story 2

- [x] T007 [US2] Implement a collapsible `<details>` element in `hbc-outlook.js` for the Analog Days list.
- [x] T008 [US2] Render the 5 analog dates (e.g., `['2026-04-12', '2026-04-11', ...]`) extracting them from the coordinator state.
- [x] T009 [US2] Implement a collapsible `<details>` element in `hbc-outlook.js` for the 24-hour graphs.
- [x] T010 [US2] Build an SVG or Canvas graphing utility within the component to plot the 288-element arrays (Import Price, Export Price, Load).
- [x] T011 [US2] Connect the graphs to the dynamic entities via the coordinator state, avoiding any hardcoded entity names.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Validation and Cleanup

- [x] T012 [P] Ensure styling is consistent with `hbc-plan-table.js` and `hbc-dashboard.js`.
- [x] T013 [P] Validate that the graph properly scales to fit the available width.
