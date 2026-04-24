# Feature Specification: Telemetry API Split

**Feature Branch**: `050-telemetry-api-split`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: User description: "if we create a new endpoint and new js to go with and keep what we have a s debug, then we can plan to reduce the data on the endpoint quite a bit more, we wont need lables and such if we are tightly in sync. plan some more for the feature with a vuew to reducing the payload while keeping the functionality. Very often the user only looks at the 30 min array, so thats a saving for a start"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Low Bandwidth Dashboard Viewing (Priority: P1)

As a user on a metered connection (e.g., via homeway.io), I want the House Battery Control dashboard to consume minimal data while idling on the screen, so that I don't exhaust my monthly data allowance.

**Why this priority**: The current 1MB payload per fetch causes massive data overages, fundamentally breaking the utility of remote monitoring. Resolving this is critical for remote users.

**Independent Test**: Can be fully tested by monitoring network traffic via browser dev tools while the dashboard is open, and delivering a >95% reduction in background data transfer.

**Acceptance Scenarios**:

1. **Given** the dashboard is open and visible on the main "Dashboard" tab, **When** 60 seconds elapses, **Then** the background data fetch should be under 5KB in size.
2. **Given** the battery state rapidly fluctuates, **When** the dashboard dynamically updates, **Then** only the lightweight telemetry payload is fetched, not the heavy plan matrices.

---

### User Story 2 - Viewing the 30-Minute Plan Array (Priority: P2)

As a user checking my battery's daily schedule, I want to view the plan in 30-minute intervals which loads instantly and consumes very little data, so that I can quickly understand the system's intent without downloading unnecessary 5-minute granular data.

**Why this priority**: Users predominantly care about the 30-minute summary rather than 5-minute fidelity. Optimizing this specific flow cuts data transfer by another 6x.

**Independent Test**: Can be fully tested by navigating to the Plan tab and verifying that the backend serves a pre-aggregated 30-minute columnar array.

**Acceptance Scenarios**:

1. **Given** the user navigates to the Plan tab, **When** the plan is loaded, **Then** a highly compressed, array-based (columnar) payload is fetched instead of an array of dictionaries.
2. **Given** the user views the 30-minute summary, **When** they do not request 5-minute data, **Then** the 5-minute data is not transmitted over the network.

---

### User Story 3 - Debugging the Full Payload (Priority: P3)

As a developer or power user troubleshooting the solver logic, I want to maintain access to the original, verbose, dictionary-based JSON payload, so that I can easily read the state transitions and sensor attributes in a human-readable format.

**Why this priority**: Retaining the old "giant JSON" ensures we don't lose our primary fault-finding mechanism during the transition.

**Independent Test**: Can be tested by directly curling or browsing the legacy endpoint and verifying the giant JSON remains intact.

**Acceptance Scenarios**:

1. **Given** a user navigates to the legacy debug endpoint, **When** the request completes, **Then** the massive 1MB payload with full labels, sensor attributes, and dictionaries is returned successfully.

### Edge Cases

- What happens if the `telemetry` API request fails due to network instability? The frontend should fall back to a reasonable retry schedule without attempting to fetch the massive 1MB payload.
- How does the system handle a user rapidly clicking between the 'Dashboard' (telemetry only) and 'Plan' (heavy) tabs? The frontend must debounce or cache the `plan` payload for at least a few seconds to prevent multiple redundant large network fetches.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a new lightweight `telemetry` API endpoint that returns only core operating variables (SoC, current power flows, FSM state, acquisition cost) and excludes any plan matrices or forecast arrays.
- **FR-002**: The system MUST expose a new `plan` API endpoint that returns forecast data strictly in a columnar array format (e.g., `{"columns": [...], "rows": [[...], ...]}`) rather than a list of repetitive dictionaries.
- **FR-003**: The `plan` endpoint MUST default to providing 30-minute aggregated intervals unless 5-minute intervals are explicitly requested by the client.
- **FR-004**: The system MUST retain the existing legacy `/hbc/api/status` endpoint completely untouched (with full labels, sensor attributes, and massive payload) for pure 1:1 legacy debugging.
- **FR-005**: The system MUST implement a completely new, lightweight production frontend panel (e.g. `hbc-panel-lite.js`) exposed at the default `/hbc-panel` URL, which uses the new `/hbc/api/telemetry` and `/hbc/api/plan` endpoints.
- **FR-006**: The system MUST retain the existing heavy frontend dashboard and expose it at a separate URL (e.g. `/hbc-debug`) for advanced troubleshooting, ensuring production users do not unintentionally trigger heavy legacy data collection.
- **FR-007**: The new production frontend MUST only fetch the `plan` payload when needed. It MUST strictly request the 30-minute interval data by default, and ONLY request the 5-minute interval data (`?resolution=5min`) if the user explicitly clicks the "5 Min" toggle.

### Key Entities

- **Telemetry Payload**: A tiny JSON object containing only the immediate state (e.g., `current_soc`, `import_power`, `fsm_state`).
- **Plan Matrix Payload**: A 2D array structure accompanied by a column-header definition, eliminating key repetition.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The background idle data transfer rate of the active dashboard MUST be reduced by at least 95% (e.g., dropping from ~1MB per fetch to under 10KB per fetch).
- **SC-002**: The JSON payload size for a 30-minute plan table view MUST be less than 20KB.
- **SC-003**: The legacy `/hbc/api/status` endpoint MUST continue to function exactly as it did in version 1.6.0-beta.21.
- **SC-004**: The user must be able to view the 30-minute and 5-minute plan tables without any loss of functionality or missing data columns compared to the legacy view.
