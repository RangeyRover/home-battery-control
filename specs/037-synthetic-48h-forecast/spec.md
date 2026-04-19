# Feature Specification: Synthetic 48h LP Solver Horizon

**Feature Branch**: `037-synthetic-48h-forecast`  
**Created**: 2026-04-19  
**Status**: Draft  
**Input**: User description: "Synthetic 48h forecast by supplementing Amber's live D+0/D+1 rates with a synthesized tail of data based on SQLite analog days matching Solcast."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analog Day Search & Synthesis (Priority: P1)

The system automatically detects when tomorrow's Solcast forecast has been updated significantly (drifts outside ± 2 kWh from the previous known target). It immediately searches the local database to find the 5 most mathematically similar historical days and calculates an average synthetic price and load shape for the D+1 and D+2 horizons.

**Why this priority**: Without this underlying engine, there is no data to drive the frontend or the LP solver. It is the core mathematical backbone of the 48h horizon.

**Independent Test**: Can be fully tested by mocking the Solcast update and verifying that the `SyntheticRatesPredictor` correctly identifies 5 valid dates from the database and returns a non-empty, averaged price curve.

**Acceptance Scenarios**:

1. **Given** a new Solcast forecast of 30 kWh and a previous target of 29 kWh, **When** the integration polls, **Then** the search is bypassed (within ± 2 kWh tolerance).
2. **Given** a new Solcast forecast of 35 kWh and a previous target of 29 kWh, **When** the integration polls, **Then** the search is triggered.
3. **Given** an executed search, **When** the query completes, **Then** it must yield exactly 5 historical days and compute their average prices.

---

### User Story 2 - Diagnostic Frontend Tab (Priority: P2)

The user can navigate to a new "Tomorrow's Outlook" tab in the House Battery Control panel to inspect the synthesized data. They can see exactly which 5 historical analog dates were chosen, what their respective solar totals were, and review the synthesized import/export price table.

**Why this priority**: Trust in the algorithm is required before wiring it into the LP solver. This diagnostic UI allows the user to manually verify the logic and "gut-check" the output.

**Independent Test**: Can be tested by mocking the backend API endpoint (`/hbc/api/synthetic_outlook`) and verifying the frontend table and statistics pane render correctly.

**Acceptance Scenarios**:

1. **Given** the user is on the HBC panel, **When** they click "Tomorrow's Outlook", **Then** the statistics pane reveals the 5 chosen dates and their target match variance.
2. **Given** the diagnostic tab is open, **When** viewing the data, **Then** a 48h table of synthesized import and export prices is rendered.

---

### User Story 3 - Extended LP Solver Horizon (Priority: P3)

The system feeds the newly synthesized 48h data tail into the Scipy LP Matrix, extending the optimization horizon from 24h (288 steps) to 48h (576 steps), allowing the battery to make smarter pre-charging decisions for consecutive cloudy days.

**Why this priority**: This is the ultimate goal, but it must wait until Phase 1 and Phase 2 (the engine and UI) are validated.

**Independent Test**: Can be tested by verifying the `coordinator.py` truncates inputs exactly to the length of the available Solcast data and successfully passes a 576-step matrix to `rates.py` without crashing.

**Acceptance Scenarios**:

1. **Given** a generated 48h synthetic curve, **When** the FSM requests a plan, **Then** the solver matrix processes exactly 576 steps.

### Edge Cases

- What happens when the SQLite database has fewer than 5 days of history? (Fallback to fewer days, or reject synthesis if < 3 days).
- How does the system handle database locking or slow query execution during the analog search? (Must run in an async executor thread).
- What happens if the backend API endpoint fails to fetch data for the diagnostic tab? (Show a graceful error message).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `SyntheticRatesPredictor` class capable of querying historical HA sensor states.
- **FR-002**: System MUST trigger an analog search when `sensor.solcast_pv_forecast_tomorrow` drifts > 2 kWh.
- **FR-003**: System MUST identify up to 5 analog days based on the absolute mathematical difference in PV generation.
- **FR-004**: System MUST expose a native HA sensor `sensor.hbc_synthetic_rates_diagnostic` to capture state passively.
- **FR-005**: System MUST serve the diagnostic data via a dedicated backend HTTP endpoint.
- **FR-006**: System MUST render a "Tomorrow's Outlook" diagnostic tab in the LitElement frontend.
- **FR-007**: System MUST support expanding the LP solver matrices (`rates.py` and `load.py`) to a max of 576 steps.

### Key Entities

- **`SyntheticRatesPredictor`**: Core logic class responsible for database lookups and mathematical averaging.
- **`sensor.hbc_synthetic_rates_diagnostic`**: Passive diagnostic entity exposing the predictor's state and timestamps.
- **`AnalogDay`**: Data structure containing a historical date, its actual PV yield, and the extracted pricing curve.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The analog SQLite search MUST return results in under 3.0 seconds to prevent event loop blocking.
- **SC-002**: The synthesized price table MUST mathematically equal the average of the retrieved historical days.
- **SC-003**: The LP solver MUST complete the 576-step calculation without timing out or breaking existing memory limits.
- **SC-004**: The UI tab MUST successfully fetch and render the diagnostic table in under 500ms.
