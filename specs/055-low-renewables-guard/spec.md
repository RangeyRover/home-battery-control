# Feature Specification: Low Renewables Guard

**Feature Branch**: `055-low-renewables-guard`  
**Created**: 2026-06-22  
**Status**: Draft  
**Input**: User description: "Detect low renewable penetration from Amber Express forecast and drive proactive battery charging behaviour, including a daytime solar capture component and overnight SoC target, to prevent high import costs during SA grid price spikes caused by low wind and low solar."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Low Renewables Detection (Priority: P1)

When the system receives Amber Electric price forecast data, it extracts the `renewables` percentage from each forecast interval. If the average renewables penetration across the upcoming 12-hour window falls below a configurable threshold (default 30%), the Low Renewables Guard activates. This detection happens automatically every coordination cycle without user intervention.

**Why this priority**: This is the core trigger. Without detection, nothing else activates. The 30% threshold is backtested against 8 known SA price spike events with a 100% hit rate for severe spikes.

**Independent Test**: Can be tested by injecting mock Amber Express forecast data with varying renewables percentages and verifying the guard activates/deactivates correctly.

**Acceptance Scenarios**:

1. **Given** Amber Express forecast intervals with average renewables of 4.9%, **When** the coordinator processes the forecast, **Then** the Low Renewables Guard activates and the system logs a warning.
2. **Given** Amber Express forecast intervals with average renewables of 65%, **When** the coordinator processes the forecast, **Then** the Low Renewables Guard remains inactive.
3. **Given** the guard is active and renewables rise above threshold, **When** the next coordinator cycle runs, **Then** the guard deactivates.
4. **Given** the user is NOT using Amber Express mode, **When** the coordinator runs, **Then** the guard detection is skipped gracefully (no errors).

---

### User Story 2 - Overnight SoC Deadline (Priority: P1)

When the Low Renewables Guard is active, the LP solver receives a deadline constraint: the battery must reach 100% SoC by 05:00 local time. The solver is free to decide *when* and *how* to reach this target — it will naturally find the cheapest overnight intervals to charge. The deadline time is configurable (default 05:00).

**Why this priority**: This is the primary protective action. By setting a hard deadline, the solver proactively charges overnight when prices are lowest, ensuring the battery enters a low-renewables day fully charged. This prevents the "ambush" scenario.

**Independent Test**: Can be tested by running the LP solver with the guard active and verifying the battery state variable reaches 100% at the deadline step index.

**Acceptance Scenarios**:

1. **Given** the guard is active with overnight deadline 05:00, **When** the LP solver runs, **Then** the battery state at the 05:00 step is constrained to 100% of capacity.
2. **Given** the guard is active, **When** the solver finds the optimal plan, **Then** the plan shows grid charging during the cheapest available overnight intervals to reach 100% by 05:00.
3. **Given** the guard is active but the battery is already at 100% SoC at 03:00, **When** the solver runs, **Then** no unnecessary additional charging occurs (the constraint is already satisfied).
4. **Given** the guard is NOT active, **When** the solver runs, **Then** the normal reserve SoC floor applies unchanged.

---

### User Story 3 - Daytime SoC Deadline (Priority: P2)

When the Low Renewables Guard is active, the LP solver receives a second deadline constraint: the battery must reach 100% SoC by 15:00 local time. This ensures that whatever solar generation is available during the day (10:00–15:00) is captured into the battery rather than exported at depressed feed-in rates. The solver decides the optimal mix of solar absorption and grid charging to meet the deadline. The deadline time is configurable (default 15:00).

**Why this priority**: On low solar winter days, even reduced solar output should be captured for battery charging. By setting a 15:00 deadline, the solver naturally favours self-consumption during solar hours and can supplement with grid charging if solar is insufficient. This ensures the battery is full before the expensive evening peak (17:00–21:00).

**Independent Test**: Can be tested by running the solver with the guard active and verifying the battery state reaches 100% at the 15:00 step index.

**Acceptance Scenarios**:

1. **Given** the guard is active with daytime deadline 15:00 and PV is generating 2 kW, **When** the solver runs, **Then** the battery state at the 15:00 step is constrained to 100% and the plan favours CHARGE or SELF_CONSUMPTION during solar hours.
2. **Given** the guard is active with daytime deadline 15:00 and PV is generating 0 kW, **When** the solver runs, **Then** the solver finds the cheapest grid charging intervals between 05:00 and 15:00 to reach 100%.
3. **Given** the guard is active but the battery is already at 100% at 12:00, **When** the solver runs, **Then** no unnecessary additional charging occurs.
4. **Given** the guard is NOT active, **When** the solver runs, **Then** no daytime deadline constraint applies.

---

### User Story 4 - Configuration Controls (Priority: P2)

The user can configure the Low Renewables Guard settings through the Home Assistant options flow. All settings have sensible defaults and are optional. The guard is enabled by default when Amber Express mode is active.

**Why this priority**: The guard must be tuneable to the user's specific circumstances (battery size, risk tolerance, local solar capacity).

**Independent Test**: Can be tested through the HA options flow by changing settings and verifying the guard responds to the new values.

**Acceptance Scenarios**:

1. **Given** the user opens the HBC options flow, **When** they navigate to the control settings, **Then** they see the Low Renewables Guard settings with defaults populated.
2. **Given** the user changes the renewables threshold from 30% to 20%, **When** the guard next evaluates, **Then** it uses the new threshold.
3. **Given** the user sets the overnight deadline to 04:00 and daytime deadline to 14:00, **When** the guard is active and the solver runs, **Then** the solver targets 100% SoC by those times.
4. **Given** the user sets peak solar reference to 35 kWh, **When** Solcast tomorrow forecast is 14 kWh (40%), **Then** the low solar condition is also flagged as a secondary trigger.

---

### User Story 5 - Dashboard Visibility (Priority: P3)

When the Low Renewables Guard is active, the dashboard displays a visual indicator showing the guard status, the current renewables percentage, and the raised SoC target. This gives the user confidence that the system is responding to the low-renewables condition.

**Why this priority**: Observability is important but not blocking. The guard should work invisibly first; dashboard is a polish item.

**Independent Test**: Can be tested by activating the guard and verifying the dashboard badge/indicator appears.

**Acceptance Scenarios**:

1. **Given** the guard is active, **When** the user views the dashboard, **Then** a visual indicator shows "Low Renewables Guard: ACTIVE" with the current renewables % and the deadline times.
2. **Given** the guard is inactive, **When** the user views the dashboard, **Then** no guard indicator is shown (clean dashboard).

---

### Edge Cases

- What happens when Amber Express data is unavailable or the `renewables` field is missing from forecast intervals? → Guard defaults to inactive (fail-safe).
- What happens when both the low-renewables trigger and the low-solar trigger fire simultaneously? → Both conditions reinforce the same action (100% SoC deadlines). No conflict — same constraints apply.
- What happens when no-import periods overlap with the solver's chosen charge window? → No-import periods always win. The solver must find alternative intervals to reach the target SoC.
- What happens when the battery is already fully charged when the guard activates? → No action needed. The constraint is already satisfied.
- What happens when electricity prices are negative during the guard period? → The solver should still charge (negative prices = paid to import). The guard SoC target reinforces this natural behaviour.
- What happens when 100% SoC by the deadline cannot be achieved? → The system targets 100% and the solver optimises toward it. Existing solver failure handling applies — no special fallback logic required.

## Clarifications

### Session 2026-06-22

- Q: How should the SoC deadline be communicated to the solver? → A: The spec defines the target (100% by deadline). The method of injecting this target into the LP solver (bounds, constraints, objective terms) is an implementation concern to be determined during planning. No special re-solve fallback required — existing solver failure handling applies.
- Q: Should the guard have hysteresis to prevent rapid on/off cycling? → A: Yes — activate at ≤30%, deactivate only when rising above 40% (10% hysteresis band).
- Q: Should deadlines apply to tomorrow's horizon when 48h synthetic data is available? → A: Yes — apply deadlines to both today and tomorrow (up to 4 constraint points) so the solver can pre-position cheaply across the full visible window.
- Q: Should the system auto-suggest peak solar reference from historical data? → A: No — manual configuration only. User sets the value (default 40 kWh). Auto-calibration is out of scope.
- Q: Should the renewables and solar triggers use OR or AND logic? → A: OR as default (either trigger independently activates the guard). Make the trigger mode configurable in controls (OR/AND) so the user can tune sensitivity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract the `renewables` percentage from each Amber Express forecast interval during the rates parsing cycle.
- **FR-002**: System MUST calculate a rolling average renewables percentage across the next 12 hours of forecast data.
- **FR-003**: System MUST activate the Low Renewables Guard when the average renewables percentage falls below the configured threshold (default 30%).
- **FR-004**: System MUST deactivate the Low Renewables Guard only when the average renewables percentage rises above the configured threshold plus a 10% hysteresis band (default 40%). This prevents rapid on/off cycling.
- **FR-005**: When the guard is active, the system MUST target 100% battery SoC by the configured overnight deadline (default 05:00 local time). When the 48h synthetic horizon is available, this target MUST also apply to tomorrow's 05:00 step. The solver is free to choose when and how to charge to meet each target.
- **FR-006**: When the guard is active, the system MUST target 100% battery SoC by the configured daytime deadline (default 15:00 local time). When the 48h synthetic horizon is available, this target MUST also apply to tomorrow's 15:00 step. The solver is free to choose any mix of solar absorption and grid charging to meet each target.
- **FR-007**: The system MUST NOT block or suppress grid export during spike risk periods — profitable sales must remain available to the solver.
- **FR-008**: System MUST provide configuration controls for: renewables threshold (%), overnight deadline time (HH:MM, default 05:00), daytime deadline time (HH:MM, default 15:00), peak solar reference (kWh, default 40), and trigger mode (OR/AND, default OR).
- **FR-009**: System MUST provide a secondary trigger based on Solcast tomorrow forecast: if forecast kWh < configured percentage (default 50%) of peak solar reference, the guard also activates. The trigger mode (default OR) determines whether either trigger independently activates the guard, or both must agree. The trigger mode is configurable in the options flow.
- **FR-010**: The guard MUST be backward-compatible — when Amber Express is not in use, the guard detection for renewables is silently skipped. The Solcast-based trigger may still operate independently.
- **FR-011**: The guard MUST NOT interfere with existing no-import periods. If no-import periods prevent charging during the solver's chosen intervals, the solver must work around them.
- **FR-012**: The system MUST expose the current guard state (active/inactive), current renewables %, and active triggers as diagnostic attributes visible on the dashboard.

### Key Entities

- **Guard State**: Active/inactive flag, current renewables average %, list of active triggers (renewables, solar, or both), and the effective target SoC being applied.
- **Renewables Timeline**: Per-interval renewables % extracted from Amber Express forecast, used for threshold evaluation.
- **Guard Configuration**: User-configurable thresholds and windows stored in the integration options.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When SA grid renewables fall below 30%, the system proactively charges the battery to 100% SoC by 05:00 and again by 15:00, reducing import costs during the subsequent peak period by at least 50% compared to the unguarded scenario.
- **SC-002**: The guard activates within one coordination cycle (≤5 minutes) of receiving low-renewables forecast data.
- **SC-003**: All guard settings are configurable through the standard options flow without requiring integration reinstallation.
- **SC-004**: The guard operates without increasing coordination cycle time by more than 100ms.
- **SC-005**: Zero regressions in existing solver behaviour when the guard is inactive — the full existing test suite passes unchanged.
- **SC-006**: The daytime solar capture window results in measurably higher self-consumption during low-solar winter days compared to unguarded behaviour.

## Assumptions

- The Amber Express forecast data reliably contains the `renewables` field in each interval. Based on live data observation, this field is consistently present.
- The 30% renewables threshold is appropriate for the SA grid based on backtesting against 8 known price spike events (5/8 hit rate at 100% when below 30%).
- The LP solver can accept SoC targets at specific step indices. The method of injection (bounds modification, additional constraints, or objective function terms) will be determined during the planning phase based on analysis of the solver's variable structure.
- The Solcast integration is available for the secondary low-solar trigger.
- Peak solar reference is a user-configured value representing the system's best-day output, not a fixed constant.

## Scope Boundaries

**In scope**:
- Amber Express renewables % extraction and threshold detection
- LP solver overnight SoC deadline constraint (100% by 05:00)
- LP solver daytime SoC deadline constraint (100% by 15:00)
- Configuration controls in options flow
- Dashboard guard status indicator
- Solcast-based secondary trigger

**Out of scope**:
- AEMO NEM scraping / fossil gap calculation (future enhancement)
- Automated peak solar calibration from historical data
- Multi-day guard persistence (guard evaluates fresh each cycle)
- Export suppression or no-export periods (user explicitly rejected this)
