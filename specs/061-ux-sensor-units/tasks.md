# Tasks: UX Sensor Units

**Input**: Design documents from `/specs/061-ux-sensor-units/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Tests are included as requested (TDD).

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- No setup tasks required for this feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- No foundational tasks required.

---

## Phase 3: User Story 1 - Clear Configuration Flow (Priority: P1)

**Goal**: The configuration flow clearly explains whether each requested sensor should be an Energy sensor or a Power sensor, with examples of the units (e.g. W/kW for Power, Wh/kWh for Energy).

**Independent Test**: Can be fully tested by running through the configuration flow and verifying that every sensor field has a clear description explaining if it's Power (W/kW) or Energy (Wh/kWh).

### Implementation for User Story 1

- [x] T001 [US1] Update `custom_components/house_battery_control/strings.json` to include detailed descriptions for all sensor config fields clarifying Power vs Energy.
- [x] T002 [US1] Update `custom_components/house_battery_control/translations/en.json` to reflect the new `strings.json` descriptions.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently in the UI.

---

## Phase 4: User Story 2 - Unit-Aware Sensor Readings (Priority: P1)

**Goal**: The integration automatically detects the unit of measurement and converts Watts to Kilowatts, and Watt-hours to Kilowatt-hours.

**Independent Test**: Can be fully tested by providing the integration with a sensor that has `unit_of_measurement: W` with value `3000`, and verifying the internal logic treats it as `3.0 kW`.

### Tests for User Story 2 (TDD) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T003 [US2] Write unit tests in `tests/test_coordinator.py` to verify `W` scales to `kW` and `Wh` scales to `kWh` when reading states.

### Implementation for User Story 2

- [x] T004 [US2] Implement unit parsing and scaling logic in `custom_components/house_battery_control/coordinator.py`.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - Dashboard Unit Display (Priority: P2)

**Goal**: The dashboard numbers are formatted clearly and consistently with their correct units (kW, kWh, $).

**Independent Test**: Can be fully tested by loading the dashboard and verifying all metrics have appropriate units and sensible formatting (e.g. not displaying 3000000 W).

### Implementation for User Story 3

- [x] T005 [US3] Update `custom_components/house_battery_control/sensor.py` (or equivalent entity definitions) to ensure exported sensors correctly reflect `kW` or `kWh` in their `unit_of_measurement` property to match the new normalized internal data.

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- No polish tasks required.

---

## Dependencies & Execution Order

### Phase Dependencies

- **User Stories (Phase 3+)**: Can proceed in sequential priority order (P1 → P2).

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies.
- **User Story 2 (P1)**: No dependencies.
- **User Story 3 (P2)**: Depends on US2 (needs normalized data from coordinator).

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD).
- Core implementation before integration.

### Implementation Strategy

#### Incremental Delivery

1. Complete User Story 1 → Test independently → Verify UI changes.
2. Complete User Story 2 (TDD) → Test independently → Verify unit scaling.
3. Complete User Story 3 → Test independently → Verify dashboard formatting.
