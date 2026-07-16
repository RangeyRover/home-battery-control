# Feature Specification: UX Sensor Units

**Feature Branch**: `061-ux-sensor-units`  
**Created**: 2026-07-16  
**Status**: Draft  
**Input**: User description: "OK, we need to adapt. i got this working for my friend. Somee feedback, its really quite tough to identify what the sensors should be in the config flow we should say ifs energy or power, but some folks dont understand the difference so we nee w or kwh and explain the difference each time a sensor is asked, also we got values from his system in w not kw so the dashboard looks screwy it does not seem to be be W or kw aware? review the dashboards and the config flow to try and make it as easy as possible."

## Clarifications

### Session 2026-07-16

- Q: If a configured sensor lacks a `unit_of_measurement` attribute, how should the integration handle it? → A: Assume kW/kWh (current default).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clear Configuration Flow (Priority: P1)

As a user setting up the integration, I want the configuration flow to clearly explain whether each requested sensor should be an Energy sensor or a Power sensor, with examples of the units (e.g. W/kW for Power, Wh/kWh for Energy), so that I don't select the wrong type of sensor.

**Why this priority**: Correct sensor selection is critical to the integration functioning properly. A confusing setup process leads to bad data and user frustration.

**Independent Test**: Can be fully tested by running through the configuration flow and verifying that every sensor field has a clear description explaining if it's Power (W/kW) or Energy (Wh/kWh), and briefly explaining the difference.

**Acceptance Scenarios**:

1. **Given** a user is configuring the integration, **When** they view a field asking for a power sensor (like Solar Power), **Then** the description clearly states it expects a Power sensor (W or kW) and explains what that means.
2. **Given** a user is configuring the integration, **When** they view a field asking for an energy sensor (like Solar Today), **Then** the description clearly states it expects an Energy sensor (Wh or kWh) and explains what that means.

---

### User Story 2 - Unit-Aware Sensor Readings (Priority: P1)

As a user whose sensors report in Watts (W) or Watt-hours (Wh) instead of kW or kWh, I want the integration to automatically detect the unit of measurement and convert it appropriately, so that the internal logic and dashboards work correctly regardless of the scale of my sensors.

**Why this priority**: Without unit awareness, a sensor reporting 3000 W will be interpreted as 3000 kW, completely breaking the solver, logic, and dashboard displays.

**Independent Test**: Can be fully tested by providing the integration with a sensor that has `unit_of_measurement: W` with value `3000`, and verifying the dashboard and internal logic treats it as `3.0 kW`.

**Acceptance Scenarios**:

1. **Given** a sensor reports a value of `5000` with unit `W`, **When** the integration reads this sensor, **Then** it converts it to `5.0` kW for internal use.
2. **Given** a sensor reports a value of `5.0` with unit `kW`, **When** the integration reads this sensor, **Then** it leaves it as `5.0` kW.
3. **Given** a sensor reports a value of `15000` with unit `Wh`, **When** the integration reads this sensor, **Then** it converts it to `15.0` kWh for internal use.

---

### User Story 3 - Dashboard Unit Display (Priority: P2)

As a user viewing the dashboard, I want the numbers to be formatted clearly and consistently with their correct units (kW, kWh, $, etc.), so that the display isn't "screwy" and is easy to understand.

**Why this priority**: A clear dashboard reinforces trust in the system's decisions.

**Independent Test**: Can be fully tested by loading the dashboard and verifying all metrics have appropriate units and sensible formatting (e.g. not displaying 3000000 W).

**Acceptance Scenarios**:

1. **Given** the dashboard is displaying power metrics, **When** it renders, **Then** the values are shown in kW (or W if appropriate) with correct labels.
2. **Given** the dashboard is displaying energy metrics, **When** it renders, **Then** the values are shown in kWh with correct labels.

### Edge Cases

- **Missing Unit Attribute**: If a sensor completely lacks a `unit_of_measurement` attribute in Home Assistant, the integration MUST fall back to assuming it is in `kW` or `kWh`.
- **Mixed Units**: Because each sensor's `unit_of_measurement` is read and normalized individually when fetching its state, a system with mixed units (e.g., Solar in `W` but Grid in `kW`) is handled automatically without any special configuration. All internal values become `kW` or `kWh`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The config flow (strings.json / en.json) MUST provide detailed descriptions for every sensor field clarifying whether it is Power (instantaneous, W/kW) or Energy (accumulated, Wh/kWh).
- **FR-002**: The integration MUST read the `unit_of_measurement` attribute of configured sensors when fetching their states.
- **FR-003**: If a Power sensor's unit is `W`, the integration MUST divide the value by 1000 to convert it to `kW` for internal processing.
- **FR-004**: If an Energy sensor's unit is `Wh`, the integration MUST divide the value by 1000 to convert it to `kWh` for internal processing.
- **FR-005**: If a sensor lacks a `unit_of_measurement`, the system MUST assume it is already in `kW` or `kWh` (default behavior) to maintain backwards compatibility, or explicitly log a warning.
- **FR-006**: The frontend dashboards MUST correctly format and display the units of the data it receives from the backend, ensuring a clean UI regardless of the raw sensor scales.

### Key Entities

- **Power Sensors**: (Solar, Grid, Battery, Load) - Represent instantaneous rate of transfer (W or kW).
- **Energy Sensors**: (Solar Today, Load Today, etc) - Represent accumulated transfer over time (Wh or kWh).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user setting up the integration for the first time can correctly identify which of their sensors are Power vs Energy without external documentation.
- **SC-002**: The integration correctly normalizes inputs from a system entirely configured with `W` and `Wh` sensors without manual user workarounds.
- **SC-003**: The dashboard displays sensible numbers (e.g. `3.5 kW` instead of `3500 kW`) when fed by Watt-based sensors.
