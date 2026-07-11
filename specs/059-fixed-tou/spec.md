# Feature Specification: Fixed TOU Support

**Feature Branch**: `059-fixed-tou`  
**Created**: 2026-07-11  
**Status**: Draft  
**Input**: User description: "Add support for Fixed Time-of-Use (TOU) tariffs. The system currently relies on dynamic pricing via Home Assistant sensors. We need to natively generate a 48-hour forward-looking price array matching the Amber JSON structure to support users with fixed TOU tariffs. Requirements: 1. Native TOU Generator generating a 48-hour array based on config values. 2. Daily Tariff Limitation: TOU settings apply as a uniform Daily schedule (Peak, Shoulder, Off-Peak). 3. Timezone & DST Handling: rely on Home Assistant OS local timezone. 4. Static Configuration Updates: Prices are updated manually via Config Flow Options and applied upon reload."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Fixed TOU Tariffs (Priority: P1)

As a user with a fixed Time-of-Use electricity plan, I want to manually configure my Peak, Shoulder, and Off-Peak times and rates within the integration's Config Flow so that I don't have to build complex Home Assistant template sensors to mimic dynamic pricing.

**Why this priority**: Without a way to input fixed TOU rates natively, users are forced to create elaborate YAML template sensors, presenting a massive barrier to entry. This is the core functionality.

**Independent Test**: Can be fully tested by configuring the integration with fixed TOU settings and verifying that the backend generates a valid 48-hour forecast array conforming to the expected Amber JSON schema.

**Acceptance Scenarios**:

1. **Given** a user is configuring the integration, **When** they select "Fixed TOU" as their pricing mode and enter rates/times, **Then** the integration saves these settings and successfully reloads.
2. **Given** the integration is running in Fixed TOU mode, **When** the rates update internally at midnight, **Then** the generated forecast array accurately reflects the configured daily schedule for the next 48 hours without raising errors.

---

### User Story 2 - Accurate Timezone and DST Handling (Priority: P1)

As a user in a region with Daylight Saving Time, I want the generated TOU schedule to accurately align with my local wall-clock time so that the battery optimally charges and discharges during the correct tariff periods even when the clocks change.

**Why this priority**: If the system fails to account for local timezones and DST, it will charge/discharge at the wrong times (e.g., an hour early or late), potentially costing the user money and defeating the purpose of the integration.

**Independent Test**: Can be tested by simulating a timezone with an upcoming DST shift (e.g., Sydney time around October/April) and verifying that the generated 48-hour forecast accurately maps the peak/off-peak windows across the time shift boundary.

**Acceptance Scenarios**:

1. **Given** the Home Assistant OS is set to a timezone with DST, **When** the system generates a 48-hour forecast that crosses a DST boundary, **Then** the start and end times of the tariff periods shift appropriately in UTC to maintain the correct local time windows.

---

### User Story 3 - Transparent Config Reloads (Priority: P2)

As a user updating my electricity contract, I want to change my Fixed TOU rates in the Config Flow and have the system begin using the new rates automatically after the integration reloads.

**Why this priority**: Users will change retailers or receive new rates periodically. They need a simple, predictable way to update the system.

**Independent Test**: Can be tested by modifying the TOU rates in the integration's options flow and verifying that the solver immediately uses the new prices on the next tick post-reload.

**Acceptance Scenarios**:

1. **Given** a running integration, **When** the user updates the Fixed TOU peak rate via the Options Flow, **Then** the integration reloads and the newly generated 48-hour forecast reflects the updated peak rate.

---

### Edge Cases

- What happens when a user configures overlapping time periods? (Validation in Config Flow should prevent this, or a deterministic fallback rule must apply).
- How does system handle a missing period (e.g., gap between 10:00 and 11:00)? (Should default to a specific tier, e.g., Off-Peak).
- What happens if the Home Assistant OS timezone is set to UTC but the user lives in Australia? (The generated forecast will strictly use the HA OS timezone; this is a user configuration issue, but we should document it).
- What happens during the 1-hour overlap when DST ends (Fall back)? (The local time repeats; the generator must handle UTC conversions carefully so the 48-hour array remains contiguous and monotonic).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a configuration interface (Config Flow Options) for users to select "Fixed TOU" mode instead of providing dynamic Home Assistant entity IDs.
- **FR-002**: System MUST allow users to configure start times, end times, and prices (import and export) for Peak, Shoulder, and Off-Peak periods.
- **FR-003**: System MUST internally generate a 48-hour forward-looking price array that mimics the Amber Electric forecast JSON structure.
- **FR-004**: System MUST apply the configured TOU schedule identically to all 7 days of the week (Daily schedule).
- **FR-005**: System MUST construct the 48-hour forecast using the Home Assistant OS local timezone, accurately accounting for Daylight Saving Time (DST) boundaries.
- **FR-006**: System MUST persist the TOU configuration and apply any changes smoothly upon integration reload.
- **FR-007**: System MUST validate that configured time periods cover the full 24-hour day without overlap, OR implement a fallback default for unconfigured hours.

### Key Entities

- **TOU Configuration Data**: Stored in the Home Assistant Config Entry. Contains the static rates and time windows for Peak, Shoulder, and Off-Peak periods.
- **Synthetic Price Forecast**: An internally generated 48-hour continuous array of pricing blocks, structually identical to the dynamic forecasts, fed into the `RatesManager`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can successfully configure a Fixed TOU tariff entirely within the integration UI without writing any YAML template sensors.
- **SC-002**: The internal TOU generator produces a valid 48-hour forecast array in less than 50 milliseconds during every coordinator update cycle.
- **SC-003**: Across a DST transition, the 48-hour forecast remains strictly contiguous (no missing or duplicated 5-minute periods in UTC).
- **SC-004**: The solver accepts the synthetic Fixed TOU forecast without requiring any algorithmic changes and correctly optimizes charge/discharge cycles based on the static schedule.
