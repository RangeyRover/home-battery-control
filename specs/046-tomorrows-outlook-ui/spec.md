# Feature Specification: Tomorrow's Outlook UI

**Feature Branch**: `046-tomorrows-outlook-ui`  
**Created**: 2026-04-20
**Status**: Draft  
**Input**: "get this into the online release tomorrows outlook only. it should show which days it was synthesized from for faultfinding manually. it should show all 3 graphs. it should be collapsible. also, the entities SHALL NOT be hardcoded, they must come from the chosen entities for price and solar"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tomorrow's Outlook Tab (Priority: P1)

Users view a dedicated "Tomorrow's Outlook" tab in the House Battery Control UI to inspect the synthesized 48-hour outlook generated from historical analog days.

**Why this priority**: It is the core feature, providing visibility into the solver's future inputs for diagnostic and fault-finding purposes.

**Independent Test**: Can be fully tested by opening the UI and navigating to the "Tomorrow's Outlook" tab to verify the graphs render.

**Acceptance Scenarios**:

1. **Given** the HBC frontend is loaded, **When** the user clicks "Tomorrow's Outlook", **Then** the UI displays the synthesized data panel.
2. **Given** the panel is visible, **When** the user clicks a collapsible section, **Then** the section expands/collapses to manage screen space.

---

### User Story 2 - Render Graphs and Analog Sources (Priority: P2)

Users inspect the exact analog days used to synthesize the forecast, and visualize the three core curves (Import Price, Export Price, Load Profile).

**Why this priority**: Critical for transparency and manual fault-finding.

**Independent Test**: Can be tested by observing the plotted curves and the list of dates from which they were synthesized.

**Acceptance Scenarios**:

1. **Given** the Tomorrow's Outlook panel is open, **When** the user views the data source section, **Then** a list of the 5 historical analog dates used for synthesis is displayed.
2. **Given** the Tomorrow's Outlook panel is open, **When** the user views the graphs section, **Then** 3 distinct graphs (Import Price, Export Price, Load) are plotted over a 24-hour axis.

---

### Edge Cases

- What happens when the analog search fails and no days are returned? (Should display a graceful error/empty state message)
- What happens if the selected pricing or load entities do not have historical data? (Graphs should render flat/empty rather than crashing)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The frontend MUST present a new tab/section labeled "Tomorrow's Outlook".
- **FR-002**: The UI MUST display a list of the historical dates that were selected as analogs for tomorrow's forecast.
- **FR-003**: The UI MUST plot the synthesized Import Price curve.
- **FR-004**: The UI MUST plot the synthesized Export Price curve.
- **FR-005**: The UI MUST plot the synthesized Load curve.
- **FR-006**: The graphs and analog days sections MUST be collapsible.
- **FR-007**: The backend and frontend MUST NOT hardcode entity IDs for pricing, solar, or load. They MUST be dynamically sourced from the integration's configuration.

### Key Entities 

- **Analog Synthesis Output**: The array of 5 selected dates, and the three 288-element arrays representing the averaged Import Price, Export Price, and Load.
- **Configuration Entities**: The user-configured `solcast_entity_id`, `import_price_entity_id`, `export_price_entity_id`, and `load_entity_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully view the 3 synthetic graphs and 5 analog dates without inspecting backend logs.
- **SC-002**: The UI gracefully collapses, allowing users to hide the 24-hour graphs to save screen real estate.
- **SC-003**: The integration successfully fetches historical data based on user-configured entities, completely eliminating hardcoded entity references.
