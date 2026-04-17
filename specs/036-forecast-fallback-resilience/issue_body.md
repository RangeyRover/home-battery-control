## Bug Report

**Version**: v1.5.7
**Severity**: High - total plan rendering failure in production
**Branch**: `036-forecast-fallback-resilience`

## Description

When using **Amber Express** (`use_amber_express: true`) but with general forecast price entities also configured, a failure or unavailability of the general forecast price entities causes **no plan to be rendered** on the dashboard.

## Steps to Reproduce

1. Enable Amber Express in the integration options
2. Configure general forecast price entities (`import_price_entity` / `export_price_entity`)
3. Amber Express is working correctly and providing valid pricing data
4. General forecast price entities become unavailable (HA restart, Amber addon crash, sensor timeout)
5. Observe that the 24-hour plan table is empty - no rows rendered

## Expected Behaviour

The system should continue to render the full 24-hour plan using Amber Express pricing data, regardless of the state of the general forecast entities. A warning should be logged but the plan should not disappear.

## Root Cause Analysis

Two fault pathways identified:

1. **Entity unavailability cascade**: `RatesManager` receives the general forecast entity IDs. When `use_amber_express=True`, it parses those same entities using the Amber Express parser. If the entities are unavailable, `attributes.get('forecasts', [])` returns empty, producing zero rates.

2. **Plan table iteration dependency**: `_build_diagnostic_plan_table` iterates over the **rates** timeline (`for idx, rate in enumerate(rates)`), not the **future_plan** array. Even when the solver produces a valid 288-step sequence, the table renders zero rows because rates is empty.

## Acceptance Criteria

- [ ] With Amber Express enabled and general forecast entities unavailable, plan table renders 288 rows
- [ ] Zero regression in existing 216-test suite
- [ ] No `UpdateFailed` exception on pricing entity unavailability
- [ ] Warning-level logs emitted for unavailable pricing entities

## Spec

See `specs/036-forecast-fallback-resilience/spec.md`
