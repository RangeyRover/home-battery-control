# Feature Specification: Solar Today Guard Trigger

**Feature Branch**: `056-solar-today-guard`  
**Created**: 2026-06-30  
**Status**: Implemented  
**Input**: User description: "Add a today solar forecast trigger to the Low Renewables Guard. If today's Solcast forecast is low, top up battery ready for the evening peak."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Today Solar Trigger Activates Guard (Priority: P1)

On a cloudy winter day, the Solcast "today" forecast shows only 8 kWh (well below the user's 40 kWh peak system). Even though Amber Express renewables may be at 50%, the guard recognises that the household will lack solar self-consumption and activates to charge the battery before the evening peak (typically 16:00–20:00).

**Why this priority**: This is the core value — the guard currently only looks at *tomorrow's* solar forecast and Amber renewables. A low-solar *today* is the most immediate signal that the evening peak will be expensive, and the battery should be topped up now.

**Independent Test**: Set Solcast today entity to a value below the threshold, verify the guard activates and the solver receives a deadline constraint for this afternoon.

**Acceptance Scenarios**:

1. **Given** Solcast today forecast is 8 kWh and the configured threshold is 50% of 40 kWh peak (= 20 kWh), **When** the coordinator runs an update cycle, **Then** the guard activates with a trigger reason containing "Solcast Today".
2. **Given** Solcast today forecast is 35 kWh (above threshold), **When** the coordinator runs an update cycle, **Then** the guard does NOT activate on the today-solar condition alone.
3. **Given** the guard activates due to today's low solar, **When** the solver runs, **Then** a deadline constraint is injected at the configured daytime deadline (default 15:00) pushing SoC toward 100%.

---

### User Story 2 — Today Solar Works With Existing Triggers (Priority: P1)

The today solar trigger integrates with the existing Amber Express renewables trigger and Solcast tomorrow trigger. In OR mode, any one of the three conditions firing activates the guard. In AND mode, all configured conditions must fire.

**Why this priority**: The guard already has a dual-trigger system. Adding a third trigger must compose correctly with the existing logic without breaking existing behaviour.

**Independent Test**: Configure OR mode with high renewables and high tomorrow solar but low today solar — verify the guard activates. Then test AND mode — verify all conditions must fire.

**Acceptance Scenarios**:

1. **Given** OR mode, high Amber renewables (65%), high Solcast tomorrow (35 kWh), but low Solcast today (5 kWh), **When** the coordinator runs, **Then** the guard activates due to "Solcast Today" trigger.
2. **Given** AND mode, low Amber renewables (5%), low Solcast tomorrow (5 kWh), but HIGH Solcast today (35 kWh), **When** the coordinator runs, **Then** the guard does NOT activate (all three must fire in AND mode).
3. **Given** AND mode, all three conditions below threshold, **When** the coordinator runs, **Then** the guard activates with all three trigger reasons listed.

---

### User Story 3 — Dashboard Shows Today Solar Trigger (Priority: P2)

When the guard activates due to today's low solar, the dashboard badge shows the "Solcast Today" trigger reason alongside any other active triggers, giving the user visibility into why the battery is charging.

**Why this priority**: Observability is important but secondary to the core logic.

**Independent Test**: Activate the guard with a low today solar value, verify the dashboard badge text includes "Solcast Today" and the kWh value.

**Acceptance Scenarios**:

1. **Given** the guard is active with a "Solcast Today" trigger, **When** the dashboard renders, **Then** the guard badge displays the trigger reason including the today forecast value.


---


### Edge Cases

- What happens when the Solcast today entity is unavailable or returns 0? The guard should treat 0 kWh as a valid low-solar value (guard activates), consistent with how tomorrow solar is handled.
- What happens when the user does not have a Solcast today entity configured? The today solar condition should be silently skipped (not trigger), and the guard falls back to the existing two-trigger logic.
- What happens in the late afternoon when today's solar has already been largely consumed? The forecast value is still valid — it represents total expected production for the day, not remaining production.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read the Solcast "today" forecast entity (already configured as `CONF_SOLCAST_TODAY_ENTITY`) and use it as a third trigger condition in the `RenewablesGuard`.
- **FR-002**: System MUST evaluate today's solar against the same configurable threshold used for tomorrow's solar (`guard_low_solar_threshold`), expressed as a percentage of the user's peak solar capacity.
- **FR-003**: System MUST compose the today solar trigger with the existing Amber Express and Solcast tomorrow triggers using the existing trigger mode (OR/AND) logic.
- **FR-004**: System MUST include "Solcast Today" in the `trigger_reasons` list when the today solar condition fires.
- **FR-005**: System MUST use the existing `guard_low_solar_threshold` config field for today's solar — no additional config field required.
- **FR-006**: System MUST gracefully handle a missing or unavailable Solcast today entity by skipping the today solar condition without errors.
- **FR-007**: Dashboard MUST display the today solar trigger reason in the guard badge when the condition fires.

### Key Entities

- **Solcast Today Forecast**: The daily total solar forecast for today (kWh), read from the existing `CONF_SOLCAST_TODAY_ENTITY` sensor.
- **Solar Threshold**: The shared configurable percentage of peak solar capacity used for both today and tomorrow solar triggers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When today's Solcast forecast is below the configured threshold, the guard activates within one coordinator update cycle (< 30 seconds).
- **SC-002**: The today solar trigger composes correctly with all existing triggers in both OR and AND modes — verified by unit tests covering all 8 combinations (3 triggers × 2 modes + edge cases).
- **SC-003**: All existing 295 tests continue to pass with zero regressions after the change.
- **SC-004**: The dashboard badge correctly displays "Solcast Today" as a trigger reason when the condition fires.
- **SC-005**: The today solar threshold shares the existing `guard_low_solar_threshold` config field — no new config required.

## Assumptions

- The Solcast today entity (`CONF_SOLCAST_TODAY_ENTITY`) already exists in the system and is configured by the user (it was added in the original Solcast integration).
- The today solar threshold uses the same `guard_low_solar_threshold` value as the tomorrow solar threshold — the user explicitly chose simplicity over independent control.
- The "today" vs "tomorrow" distinction maps to the existing `sensor.solcast_pv_forecast_forecast_today` and `sensor.solcast_pv_forecast_forecast_tomorrow` HA entities.

## Clarifications

### Session 2026-06-30

- Q: Should the today solar threshold be separate from the tomorrow threshold? → A: Share the same threshold — simpler config, one value for both.
