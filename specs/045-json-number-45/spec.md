# Feature Specification: Local Analog Testing

**Feature Branch**: `045-json-number-45`  
**Created**: 2026-04-20
**Status**: Draft  
**Input**: User description: "what i require is a local implementation of the system requirements to identify 5 most recent days of statistics most closely matching tomorrows forecast. for the purposes of testing, prove that we can do this at 28,26,24,22, 20, 18, 16,14 kwh of solar for tomorrow. the aim is to prove that we can do this locally and then implement this method in the online release for testing. sdd, tdd tests before code. review all artefacts as we have doen this before but it seems we have forgottent in the db is in test data"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Local Test Verification (Priority: P1)

As a developer, I want to prove the analog search algorithm logic locally against a test database before applying it to the live integration, so that I can confidently ensure the system correctly extracts the closest 5 matching historical days for any given forecast target.

**Why this priority**: It is critical to prove the exact search logic works locally with the test database to avoid regressions or errors in the online build (e.g. timezone offsets, missing data).

**Independent Test**: Can be fully tested by running a local Python script or `pytest` suite that queries the test DB (`home-assistant_v2.db`) for targets: 28, 26, 24, 22, 20, 18, 16, and 14 kWh.

**Acceptance Scenarios**:

1. **Given** a target of 28 kWh, **When** the local extraction method is run, **Then** it returns the 5 most recent days with maximum PV yield within a 5% tolerance (or the 5 closest days by absolute error if fewer than 5 exist).
2. **Given** a target of 14 kWh, **When** the local extraction method is run, **Then** it gracefully falls back and successfully extracts the 5 closest matching days.

---

### User Story 2 - Online Implementation (Priority: P2)

As a developer, after proving the logic locally, I want to implement the exact same method in the online release (`rates_predictor.py`), so that the Home Assistant integration reliably generates the 48h Synthetic Outlook.

**Why this priority**: The ultimate goal is a working live integration, but it strictly depends on the success of P1.

**Independent Test**: Can be fully tested by verifying the live integration loads the Synthetic Outlook panel without throwing exceptions for tomorrow's forecast.

**Acceptance Scenarios**:

1. **Given** the local method passes all tests, **When** it is ported to the integration, **Then** the online system executes the search without tracebacks.

### Edge Cases

- What happens when there are fewer than 5 total days in the local database?
- How does the system handle database timezone conversions (UTC to Local) to ensure dates align perfectly with the target forecast day?
- How does the system handle cases where the Solcast forecast entity lacks `state_class` and is not present in the `statistics_meta` table?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST implement a local test script or suite querying `tests/test_data/home-assistant_v2.db`.
- **FR-002**: The local test MUST accept a sweep of forecast targets: 28, 26, 24, 22, 20, 18, 16, 14 kWh.
- **FR-003**: The local test MUST output the 5 selected analog dates and their corresponding PV yields for each target to prove correctness.
- **FR-004**: The system MUST apply a 5-day graceful degradation rule (fallback to closest by absolute error if <5 days found within 5% tolerance).
- **FR-005**: The system MUST handle correct timezone conversions from the DB's UTC timestamps to the local timezone.
- **FR-006**: The local logic MUST be ported to the online integration (`rates_predictor.py`) once local tests pass.

### Key Entities

- **Analog Day**: Represents a historical day matching the forecast, containing the Date and Max PV Yield.
- **Test Database**: The SQLite `home-assistant_v2.db` containing a snapshot of historical statistics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The local test suite executes 100% successfully for all specified target values (28 to 14).
- **SC-002**: The local test outputs exactly 5 distinct historical days for each target.
- **SC-003**: The logic is successfully transferred to the live integration and Tomorrow's Outlook renders without errors.
