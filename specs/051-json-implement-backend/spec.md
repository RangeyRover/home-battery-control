# Feature Specification: Server-Side Plan Matrix Aggregation

**Feature Branch**: `051-json-implement-backend`  
**Created**: 2026-04-25  
**Status**: Draft  
**Input**: User description: "Implement backend server-side 30-minute plan aggregation for the /hbc/api/plan endpoint. The backend must do the 30 min chunking to bring payload under 20kb"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Viewing the Default 30-Minute Plan Matrix (Priority: P1)

As a user loading the HBC dashboard Plan tab, I want the system to automatically send me a highly compressed 30-minute aggregated view of the plan matrix, so that the data transfer is under 20KB and loads instantly even on slow cellular connections.

**Why this priority**: The previous implementation shifted filtering to the frontend, which meant 128KB of 5-minute data was still transmitted over the network. This defeats the purpose of extreme bandwidth minimization for mobile users checking the daily plan.

**Independent Test**: Can be fully tested by making an HTTP request to `/hbc/api/plan` (without any query parameters) and verifying that the response payload string length is strictly under 20KB, and that it contains ~48 rows (for a 24-hour period) instead of 288.

**Acceptance Scenarios**:

1. **Given** the user requests the plan endpoint without a resolution parameter, **When** the backend generates the matrix, **Then** it must aggregate the 5-minute rows into 30-minute chunks.
2. **Given** the 30-minute chunks are generated, **When** calculating values, **Then** continuous variables (power, temp, prices) are averaged, cumulative values are preserved from the last interval, and FSM states are correctly elevated if charging/discharging occurs in the window.

---

### User Story 2 - Accessing 5-Minute High-Fidelity Data (Priority: P2)

As a power user diagnosing a specific 5-minute interval decision, I want to explicitly request the full unaggregated 5-minute plan matrix from the API, so that I can see exactly what the solver decided at every step.

**Why this priority**: Users still need access to the full 5-minute data matrix if they explicitly toggle it in the UI.

**Independent Test**: Can be fully tested by making an HTTP request to `/hbc/api/plan?resolution=5min` and verifying the payload contains the full 288+ rows.

**Acceptance Scenarios**:

1. **Given** the user explicitly requests the 5-minute resolution via query parameters, **When** the backend processes the request, **Then** it must bypass the 30-minute aggregation and return the full high-fidelity matrix.

### Edge Cases

- What happens if the `plan` matrix array does not cleanly divide into 30-minute blocks? The aggregation logic must gracefully handle trailing chunks by aggregating whatever remains up to the end of the data.
- How does the aggregation handle FSM state strings? If a 30-minute block contains a mix of `SELF_CONSUMPTION` and `CHARGE_GRID`, the system must elevate the state to `CHARGE_GRID` (or `DISCHARGE_GRID`) to ensure the user does not miss critical grid actions visually.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `/hbc/api/plan` endpoint MUST accept an optional `resolution` query parameter.
- **FR-002**: The default behavior (if `resolution` is omitted or set to `30min`) MUST be to aggregate the underlying 5-minute solver data into 30-minute intervals before matrix serialization.
- **FR-003**: If `resolution=5min` is requested, the endpoint MUST return the unaggregated 5-minute fidelity data.
- **FR-004**: The 30-minute aggregation logic MUST correctly average numerical rates (e.g., Import Rate, PV Forecast, Load Forecast) across the 6 intervals.
- **FR-005**: The 30-minute aggregation logic MUST correctly summarize FSM states by elevating active grid states (`CHARGE_GRID`, `DISCHARGE_GRID`) above `SELF_CONSUMPTION`.
- **FR-006**: The frontend Plan Table (`hbc-plan-table-lite.js`) MUST be updated to fetch from the API when the resolution toggle is switched, rather than filtering the data locally.

### Key Entities

- **Aggregated Plan Matrix**: A columnar JSON structure (`columns`, `rows`) where the rows represent 30-minute intervals instead of 5-minute intervals.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The JSON payload size for the default `/hbc/api/plan` response MUST be strictly less than 20KB.
- **SC-002**: The length of the `rows` array in the default plan matrix response MUST be approximately 1/6th the length of the 5-minute plan.
- **SC-003**: The frontend Plan table MUST visually display the exact same aggregated values (to 2 decimal places) as the previous JavaScript-based local filtering implementation.
