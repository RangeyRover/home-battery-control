# Feature Specification: Frontend Testing & Persistent System Requirements

**Feature Branch**: `039-frontend-testing`  
**Created**: 2026-04-18  
**Status**: Draft  
**Input**: User description: "for the system requirements and tests I wan the system requirements to be a persisten artefact that we add to with each feature run"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Formalize System Requirements Artifact (Priority: P1)

As a developer, I want the central `system_requirements.md` to be formally recognized as a persistent, living artifact, so that every new feature explicitly updates it and preserves a single source of truth for system behavior.

**Why this priority**: Without a central source of truth, reverse-engineering requirements (as seen with the frontend components) becomes a repetitive and error-prone task. Establishing this rule is foundational.

**Independent Test**: Can be verified by updating the `system_requirements.md` with the new frontend requirements and observing that the project documentation accurately reflects the current state of the application.

**Acceptance Scenarios**:

1. **Given** the repository state, **When** a new feature alters behavior, **Then** the `system_requirements.md` must be updated as part of the feature lifecycle.
2. **Given** the newly refactored frontend components, **When** reviewing `system_requirements.md`, **Then** it must contain explicit behavioral requirements for `<hbc-dashboard>`, `<hbc-sensors>`, and `<hbc-plan-table>`.

---

### User Story 2 - Establish JavaScript Testing Framework (Priority: P2)

As a developer, I want a JavaScript testing framework installed and configured, so that I can rigorously test the LitElement web components using Test-Driven Development (TDD).

**Why this priority**: The frontend logic is complex and handles formatting, local storage, and math. It needs automated regression testing just like the Python backend.

**Independent Test**: Can be verified by running `npm test` and seeing successful execution of a basic test suite without errors.

**Acceptance Scenarios**:

1. **Given** a clean repository, **When** running `npm install`, **Then** the required testing dependencies (`@web/test-runner`, `@open-wc/testing`) are installed successfully.
2. **Given** the testing framework is installed, **When** running `npm test`, **Then** the tests execute headlessly without requiring manual browser interaction.

---

### User Story 3 - Implement Web Component Tests (Priority: P3)

As a developer, I want comprehensive unit tests for the three new LitElement components, so that their rendering, math, and persistence logic are automatically verified.

**Why this priority**: Directly implements the reverse-engineered requirements and locks them against regression.

**Independent Test**: Can be fully tested by running `npm test` and observing a 100% pass rate for the specific component tests.

**Acceptance Scenarios**:

1. **Given** the `hbc-dashboard` component, **When** provided with a mock payload, **Then** it must correctly calculate and render the 24-hour summary stats.
2. **Given** the `hbc-sensors` component, **When** a user toggles visibility, **Then** the state must be correctly persisted to `localStorage`.
3. **Given** the `hbc-plan-table` component, **When** the resolution is switched to 30-minutes, **Then** the rows must accurately average their numerical values and properly extract boundary states.

---

### Edge Cases

- What happens if the `localStorage` contains malformed JSON for the hidden columns? (System should gracefully fall back to default empty state).
- How does the test suite handle the lack of a real Home Assistant API backend? (It must use mocked data payloads).
- How do we handle `system_requirements.md` merge conflicts if multiple features update it simultaneously? (Standard Git conflict resolution applies, but the file structure must be modular enough to minimize overlap).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST include a `package.json` with `@web/test-runner` and `@open-wc/testing` configured for LitElement components.
- **FR-002**: System MUST include a test suite for `hbc-dashboard` that verifies rendering, the "Power Flow" grid, the "Status Grid", and the 24-hour forecast math.
- **FR-003**: System MUST include a test suite for `hbc-sensors` that verifies rendering, toggle behavior, and `localStorage` persistence.
- **FR-004**: System MUST include a test suite for `hbc-plan-table` that verifies row rendering, 30-minute chunking logic, boundary state extraction, and `localStorage` column toggling.
- **FR-005**: The `system_requirements.md` MUST be explicitly updated to include the behavioral specifications of the three frontend components.
- **FR-006**: The specification workflow MUST dictate that `system_requirements.md` is a persistent artifact updated by every new feature that alters system behavior.

### Key Entities 

- **System Requirements Artifact**: The `system_requirements.md` file in the root directory acting as the single source of truth.
- **JS Test Suite**: The collection of `.test.js` files utilizing the Web Test Runner environment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the reverse-engineered frontend requirements are explicitly documented in `system_requirements.md`.
- **SC-002**: `npm test` executes and passes 100% of the tests for the three frontend components without manual intervention.
- **SC-003**: The JS test suite executes completely in under 10 seconds.
