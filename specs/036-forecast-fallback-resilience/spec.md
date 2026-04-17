# Feature Specification: Forecast Fallback Resilience (BUG-036)

**Feature Branch**: `036-forecast-fallback-resilience`  
**Created**: 2026-04-17  
**Status**: Draft  
**Severity**: High — total plan rendering failure in production  
**Affected Version**: v1.5.7  
**Input**: User fault report: "When using Amber Express but with general forecast prices also configured, a failure in the general forecast prices will cause no plan to be rendered."

## Problem Statement

When a user has **Amber Express** enabled (`use_amber_express: true`) AND has both the general forecast price entities and Amber Express price entities configured, the system wires the Amber Express parser to the **wrong entity IDs**, causing the 24-hour pricing timeline to be empty or broken.

## Root Cause Analysis — Entity Wiring Defect

### The configuration UI exposes five price-related fields:

| UI Field | Config Key | User's Entity |
|---|---|---|
| Import Price Forecast Entity | `CONF_IMPORT_PRICE_ENTITY` | `4 Rosella - General Forecast` |
| Export Price Forecast Entity | `CONF_EXPORT_PRICE_ENTITY` | `4 Rosella - Feed In Forecast` |
| Use Amber Express | `CONF_USE_AMBER_EXPRESS` | `true` |
| Import Price Entity (Amber Express) | `CONF_CURRENT_IMPORT_PRICE_ENTITY` | `General Price Detailed` |
| Export Price Entity (Amber Express) | `CONF_CURRENT_EXPORT_PRICE_ENTITY` | `Feed In Price Detailed` |

### The wiring defect:

The `RatesManager` is constructed in `coordinator.py` as:

```
RatesManager(
    hass,
    config.get(CONF_IMPORT_PRICE_ENTITY),    ← General Forecast entity
    config.get(CONF_EXPORT_PRICE_ENTITY),    ← General Forecast entity
    use_amber_express=True,                  ← switch to Express parser
)
```

When `use_amber_express=True`, the system applies the **Amber Express parser** (`_parse_amber_express_entity`) to the **General Forecast entities**. But:

- General Forecast entities have attribute `forecast` (standard Amber 30-minute blocks)
- Amber Express entities have attribute `forecasts` (nested 5-minute express arrays with `renewables`, `advanced_price_predicted`, etc.)

The Express parser looks for `state.attributes.get("forecasts", [])` on the General Forecast entity → gets an empty list → produces zero rates.

Meanwhile, the actual Amber Express entities (`General Price Detailed` / `Feed In Price Detailed`) are wired to `CONF_CURRENT_IMPORT_PRICE_ENTITY` / `CONF_CURRENT_EXPORT_PRICE_ENTITY`, which the coordinator **only uses for instantaneous row-0 price override** — not the 24-hour forecast.

### Impact:

- The 24-hour pricing timeline is empty (zero rates)
- The LP solver runs with all-zero prices, producing a degenerate SELF_CONSUMPTION plan
- `_build_diagnostic_plan_table` iterates over the empty rates list, rendering zero table rows
- The dashboard shows no plan

### Secondary fault — Plan table coupling:

Even if the rates were partially populated, the `_build_diagnostic_plan_table` method iterates over the **rates timeline** (`for idx, rate in enumerate(rates)`) rather than the **future_plan** array. This means the plan table row count is coupled to the rates list length, not the solver output.

## User Scenarios & Testing

### User Story 1 — Amber Express Entities Used for 24h Forecast (Priority: P1)

When a user enables Amber Express and configures Amber Express price entities (in the `current_import_price_entity` / `current_export_price_entity` fields), the system must use those entities for the full 24-hour pricing timeline, not just for instantaneous row-0 override.

**Why this priority**: This is the primary wiring defect. Without this fix, Amber Express users get no meaningful pricing data in the solver.

**Independent Test**: Configure Amber Express entities with valid `forecasts` data, enable `use_amber_express`, verify the rates list is populated with express-parsed pricing from the correct entities.

**Acceptance Scenarios**:

1. **Given** Amber Express is enabled and express entities are configured in `current_import_price_entity` / `current_export_price_entity`, **When** the coordinator updates, **Then** `RatesManager` parses the express entities (not the general forecast entities) for the full 24-hour timeline.
2. **Given** Amber Express is enabled but only general forecast entities are configured (no express entities), **When** the coordinator updates, **Then** the system falls back to parsing the general forecast entities using the standard parser.
3. **Given** Amber Express is enabled and express entities are configured, **When** the express entities become temporarily unavailable, **Then** the system falls back to the general forecast entities.

---

### User Story 2 — Plan Table Renders from Solver Output (Priority: P2)

The diagnostic plan table must render based on the solver's future plan output, not the rates timeline length.

**Why this priority**: This is the secondary mechanism that causes a blank table even when the solver produces valid output.

**Independent Test**: Pass empty rates but valid 288-step `future_plan` to `_build_diagnostic_plan_table`; verify 288 rows render.

**Acceptance Scenarios**:

1. **Given** the rates timeline has fewer intervals than the solver's future plan, **When** the plan table is built, **Then** the table renders rows for all solver steps, using solver-embedded pricing data where rates are missing.
2. **Given** the rates timeline is empty, **When** the solver has produced a valid 288-step plan, **Then** the plan table still renders all 288 steps.

---

### User Story 3 — Dashboard Communicates Degraded State (Priority: P3)

When the system is operating with fallback pricing (e.g., general forecast instead of express, or zero-price defaults), the dashboard should visually indicate degraded operation.

**Why this priority**: User awareness prevents confusion during transient failures.

**Independent Test**: Trigger a pricing entity fallback and verify the dashboard shows a degradation indicator.

**Acceptance Scenarios**:

1. **Given** one or more pricing entities are unavailable, **When** the dashboard renders, **Then** a visible warning indicator appears.

---

### Edge Cases

- What happens when both express AND general forecast entities are unavailable simultaneously? → System should still render a degraded plan (all-zero prices, SELF_CONSUMPTION) rather than a blank table.
- What happens when `use_amber_express` is true but `current_import_price_entity` is NOT configured? → System should fall back to parsing `import_price_entity` with the standard parser, not the express parser.
- What happens when express entities are configured but return empty `forecasts` arrays? → System should fall back to general forecast entities.
- What happens when rates are available but have fewer than 288 intervals? → Plan table should pad/extend to match full 288-step solver output.

## Requirements

### Functional Requirements

- **FR-001**: When `use_amber_express` is enabled AND `current_import_price_entity` / `current_export_price_entity` are configured, the `RatesManager` MUST use those entities (not `import_price_entity` / `export_price_entity`) for the 24-hour pricing forecast.
- **FR-002**: When `use_amber_express` is enabled but express entities are NOT configured or are unavailable, the system MUST fall back to parsing the general forecast entities using the standard parser (`_parse_entity`), NOT the express parser.
- **FR-003**: The diagnostic plan table builder MUST NOT depend exclusively on the rates timeline length. If the solver's future plan is longer than the rates list, the table MUST extend to cover the full solver output.
- **FR-004**: When a pricing entity is unavailable, the system MUST log a warning but MUST NOT abort the update cycle.
- **FR-005**: Existing behaviour for users who do NOT have Amber Express enabled MUST NOT be affected.
- **FR-006**: The UI labels for `current_import_price_entity` / `current_export_price_entity` SHOULD be clarified to communicate that these are the primary data source for Amber Express mode.

### Key Entities

- **RatesManager**: Must be modified to accept and prefer express entity IDs when available, falling back to general forecast entities.
- **Coordinator**: Must pass the correct entity IDs to `RatesManager` based on configuration.
- **Diagnostic Plan Table**: Must decouple row count from rates timeline length.
- **Config Flow / Translations**: UI labels should clarify the relationship between the entity fields and Amber Express mode.

## Success Criteria

### Measurable Outcomes

- **SC-001**: With Amber Express enabled and express entities configured, the rates list is populated from the express entities — verified by automated test.
- **SC-002**: With Amber Express enabled and express entities unavailable, the system falls back to general forecast entities — verified by automated test.
- **SC-003**: With empty rates, the plan table renders 288 rows when the solver produces a 288-step plan — verified by automated test.
- **SC-004**: Zero regression in the existing 216-test suite.
- **SC-005**: No `UpdateFailed` exception raised when pricing entities are unavailable.

## Assumptions

- The Amber Express `forecasts` attribute structure has not changed from the format documented in Feature 029.
- The `current_import_price_entity` / `current_export_price_entity` config keys can be safely repurposed to serve as both the express forecast source AND the instantaneous price source, since Amber Express entities provide both.
- General forecast entities (`import_price_entity` / `export_price_entity`) will remain configured alongside express entities for fallback purposes.
