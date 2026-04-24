# Feature Specification: Coordinator Strangler Pattern

**Feature Branch**: `042-coordinator-strangler`  
**Created**: 2026-04-19  
**Status**: Draft  
**Input**: User description: "Implement a strangler pattern on the coordinator to reduce its size"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Maintain Integration Stability During Refactor (Priority: P1)

As a developer, I want to extract distinct responsibilities from the monolithic `coordinator.py` into smaller, focused modules one by one (Strangler Fig pattern), so that I can reduce technical debt and file size without breaking the live system.

**Why this priority**: Refactoring the core coordinator is high risk. The strangler pattern ensures the system remains fully functional at every intermediate step.

**Independent Test**: Can be fully tested by verifying that all unit tests (`pytest`) continue to pass after each incremental extraction, and that the integration initializes normally in Home Assistant.

**Acceptance Scenarios**:

1. **Given** the monolithic coordinator, **When** a single responsibility (e.g., FSM Context building or Sensor Fetching) is extracted to a new module, **Then** the coordinator delegates to the new module and all tests pass.
2. **Given** the new modular architecture, **When** the integration runs a full update cycle, **Then** the exact same inputs are passed to the LP solver as before.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The refactoring MUST follow the Strangler Fig pattern, meaning responsibilities are extracted incrementally rather than rewriting the coordinator from scratch.
- **FR-002**: The `coordinator.py` file size MUST be significantly reduced.
- **FR-003**: Extracted modules MUST adhere to the Single Responsibility Principle (SRP).
- **FR-004**: Existing test coverage MUST be maintained or improved during the extraction.
- **FR-005**: The core update loop and Home Assistant `DataUpdateCoordinator` lifecycle MUST NOT be fundamentally altered.

### Key Entities

- **`HouseBatteryCoordinator`**: The main class. It will transition from doing all the work to orchestrating calls to the extracted modules.
- **Data Fetchers / Builders**: New classes/modules to be created (e.g., `FSMContextBuilder`, `SensorDataFetcher`) that encapsulate specific domain logic previously housed in the coordinator.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The line count of `coordinator.py` is reduced by at least 40% (target < 500 lines).
- **SC-002**: The test suite continues to pass with 0 regressions.
- **SC-003**: The Home Assistant integration maintains identical operational behavior (no functional changes to the end-user or battery planning).
