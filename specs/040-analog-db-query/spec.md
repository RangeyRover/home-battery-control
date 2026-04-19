# Feature Specification: Analog DB Query

**Feature Branch**: `040-analog-db-query`  
**Created**: 2026-04-19  
**Status**: Draft  
**Input**: User description: "start from the beginning to get the price data from the dtabase for the 5 most recent matching solar days"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve Historical Analog Data (Priority: P1)

The system automatically searches the local Home Assistant SQLite database to find the 5 historical days that most closely match a target solar PV yield. Once identified, the system extracts the historical electricity pricing curves for those specific 5 days.

**Why this priority**: Without extracting this core data from the database, the synthetic forecast has no foundational pricing information to base its forward-looking math upon.

**Independent Test**: Can be fully tested by triggering the search via a python unit test or the Home Assistant Developer Tools, and verifying that the database correctly returns 5 historical days with a fully populated 288-step pricing curve for each.

**Acceptance Scenarios**:

1. **Given** a target PV yield, **When** the database search executes, **Then** it must return the 5 historical dates with the absolute smallest difference in PV yield.
2. **Given** the 5 identified analog dates, **When** extracting the pricing curve, **Then** it must return a normalized array of historical pricing values spanning the full 24-hour period for each date.

---

### Edge Cases

- What happens when there are fewer than 5 days of history available in the Home Assistant recorder database?
- How does the system handle historical days where the pricing sensor was partially unavailable (missing data)?
- What happens if the pricing entity is completely missing from the recorder history?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST connect to the Home Assistant `recorder` database API to execute historical queries without blocking the main thread.
- **FR-002**: System MUST identify the 5 historical days with the smallest absolute difference between their actual/forecasted PV yield and the current target PV yield.
- **FR-003**: System MUST extract the historical state changes of the designated pricing entity for the selected 5 days.
- **FR-004**: System MUST normalize the irregular historical state changes into a fixed-interval array (e.g., 288 5-minute steps) representing the full 24-hour pricing curve for each day.
- **FR-005**: System MUST extract the import pricing curves, export pricing curves, and historical load profiles for the identified 5 analog days.

### Key Entities

- **AnalogDay**: A data structure containing the historical date, its matching PV yield, and its extracted historical pricing array.
- **Home Assistant Recorder API**: The core database interaction layer (`homeassistant.components.recorder.history.get_significant_states`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The database query correctly identifies and returns the 5 analog days within 1.5 seconds of execution to prevent blocking the Home Assistant event loop.
- **SC-002**: The extracted pricing arrays are perfectly normalized to 288 steps, regardless of how frequently the pricing sensor historically updated.
- **SC-003**: The system safely falls back or handles exceptions if the database is corrupt or missing data, preventing an integration crash.
