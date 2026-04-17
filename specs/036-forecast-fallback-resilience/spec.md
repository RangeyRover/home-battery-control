# Feature Specification: Forecast Fallback Resilience (BUG-036)

**Feature Branch**: `036-forecast-fallback-resilience`  
**Created**: 2026-04-17  
**Status**: Draft  
**Severity**: High — total plan rendering failure in production  
**Affected Version**: v1.5.7  
**Input**: User fault report: "When using Amber Express but with general forecast prices also configured, a failure in the general forecast prices will cause no plan to be rendered."

## Problem Statement

When a user has **Amber Express** enabled (`use_amber_express: true`) AND has the general forecast price entities (`import_price_entity` / `export_price_entity`) also configured, a failure or unavailability of the general forecast price entities causes the **entire 24-hour plan to disappear from the dashboard**.

This is a fault tolerance deficiency. The system should gracefully degrade: if Amber Express is the active pricing source and is healthy, the plan should still render regardless of the state of any co-configured general forecast entities.

## Root Cause Analysis

The `RatesManager` is constructed with the general forecast entity IDs (`CONF_IMPORT_PRICE_ENTITY` / `CONF_EXPORT_PRICE_ENTITY`). When `use_amber_express=True`, the `update()` method routes to `_parse_amber_express_entity()` using those same entity IDs.

The fault mechanism has two potential pathways:

1. **Entity unavailability cascade**: When the general forecast entity becomes unavailable (HA restart, Amber addon crash, network timeout), its state transitions to `unavailable`/`unknown`. The Amber Express parser looks for `state.attributes.get("forecasts", [])` — on an unavailable entity, attributes may be empty or the entity may not resolve, producing zero rates. With zero rates, `_build_diagnostic_plan_table` iterates over an empty `rates` list and produces zero table rows — rendering no plan.

2. **Diagnostic plan table dependency**: The `_build_diagnostic_plan_table` method (coordinator.py) iterates over the **rates** timeline — not the **future_plan** array. Even if the solver successfully ran with all-zero prices and produced a valid 288-step sequence, the diagnostic plan table renders zero rows because the outer loop is `for idx, rate in enumerate(rates)`.

## User Scenarios & Testing

### User Story 1 — Plan Survives General Forecast Failure (Priority: P1)

A user has configured Amber Express as their pricing source. They have also previously configured general forecast price entities (which may have been used before Amber Express was enabled). When those general forecast entities become unavailable (HA restart, sensor failure), the 24-hour plan continues to display correctly using Amber Express data.

**Why this priority**: This is the core defect. The user's system loses all planning visibility during entity failures, defeating the purpose of the battery optimisation system.

**Independent Test**: Configure `use_amber_express: true` with valid Amber Express data, set general forecast entities to `unavailable`, verify the plan table still renders with 288 rows.

**Acceptance Scenarios**:

1. **Given** Amber Express is enabled and healthy, **When** the general forecast price entities become unavailable, **Then** the 24-hour plan table renders with the correct number of rows using Amber Express pricing data.
2. **Given** Amber Express is enabled and healthy, **When** the general forecast price entities return `unknown` state, **Then** the system logs a warning but continues to render the full plan.
3. **Given** Amber Express is enabled and healthy, **When** the general forecast price entities have empty `forecast` attributes, **Then** the plan still renders using the Amber Express `forecasts` attribute.

---

### User Story 2 — Solver Produces Valid Plan Despite Empty Rates (Priority: P2)

When the rates timeline is empty for any reason, the LP solver should still produce a 288-step future plan. The diagnostic plan table should be able to render the plan using the solver's own output rather than depending on a populated rates list.

**Why this priority**: This is the secondary mechanism — even if the rates are empty, the solver already runs and produces output. The issue is that the plan table rendering discards that output.

**Independent Test**: Pass empty rates to `_build_diagnostic_plan_table` but provide a valid 288-step `future_plan` array; verify 288 rows are rendered.

**Acceptance Scenarios**:

1. **Given** the rates timeline is empty, **When** the solver has produced a valid 288-step future plan, **Then** the diagnostic plan table renders all 288 steps using the solver's embedded price data.
2. **Given** the rates timeline has fewer intervals than the future plan, **When** the plan table is built, **Then** the table extends to cover all solver steps, not just the rate intervals.

---

### User Story 3 — Dashboard Communicates Degraded State (Priority: P3)

When the system is operating in a degraded mode (e.g., using fallback pricing, missing forecast entities), the dashboard should visually indicate which data sources are healthy and which are degraded.

**Why this priority**: User awareness of degraded operation prevents confusion and supports troubleshooting.

**Independent Test**: Trigger a forecast entity failure and verify the dashboard displays a visible degradation indicator.

**Acceptance Scenarios**:

1. **Given** one or more forecast entities are unavailable, **When** the dashboard renders, **Then** a visible warning indicator appears showing which data sources are degraded.

---

### Edge Cases

- What happens when **both** Amber Express AND general forecast entities are unavailable simultaneously? System should still render a degraded plan (all-zero prices, SELF_CONSUMPTION states) rather than a blank table.
- What happens when Amber Express entities are configured but return empty `forecasts` arrays? System should fall back gracefully with appropriate logging.
- What happens when rates are available but have fewer than 288 intervals? The plan table should pad/extend to match the full 288-step solver output.

## Requirements

### Functional Requirements

- **FR-001**: When `use_amber_express` is enabled and the Amber Express entity returns valid `forecasts` data, the system MUST produce a full 24-hour plan regardless of the state of any co-configured general forecast entities.
- **FR-002**: The diagnostic plan table builder MUST NOT depend exclusively on the rates timeline length for its iteration count. If the rates timeline is shorter than the solver's future plan, the table MUST extend to cover the full solver output.
- **FR-003**: When a pricing entity is unavailable, the system MUST log a warning at `WARNING` level including the entity ID and failure reason, but MUST NOT abort the update cycle.
- **FR-004**: When all pricing sources fail simultaneously, the system MUST still produce a valid (albeit degraded) 288-step plan using zero-price defaults, resulting in SELF_CONSUMPTION for all intervals.
- **FR-005**: Existing behaviour for users who do NOT have Amber Express enabled MUST NOT be affected.

### Key Entities

- **RatesManager**: Responsible for parsing pricing data from configured entities; must be resilient to entity unavailability.
- **Diagnostic Plan Table**: The `_build_diagnostic_plan_table` method in the coordinator; must decouple its row count from the rates timeline.
- **Solver Inputs Builder**: The `_build_solver_inputs` method; already handles empty rates gracefully (produces zero-price arrays).

## Success Criteria

### Measurable Outcomes

- **SC-001**: With Amber Express enabled and general forecast entities set to `unavailable`, the plan table renders exactly 288 rows — verified by automated test.
- **SC-002**: Zero regression in the existing 216-test suite — all tests continue to pass.
- **SC-003**: No `UpdateFailed` exception is raised when pricing entities are unavailable — the coordinator update cycle completes successfully.
- **SC-004**: Warning-level log entries are emitted for each unavailable pricing entity, enabling user troubleshooting.

## Assumptions

- The Amber Express `forecasts` attribute structure has not changed from the format documented in Feature 029.
- The user's Amber Express entities and general forecast entities may share the same entity IDs (when the same sensor is parsed differently based on `use_amber_express`), or may be distinct entities.
- The `_build_diagnostic_plan_table` fix should use the `future_plan` length as the primary iteration driver, falling back to `rates` for supplementary data (timestamps, pricing) where available.
