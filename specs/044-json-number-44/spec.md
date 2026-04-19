# Feature Specification: Online Analog DB Method

## Overview
This feature transfers the proven analog search algorithm (which was developed and validated against a local SQLite Home Assistant database) into the live `house_battery_control` integration. The goal is to safely replace the current faulty historical data extraction method in `rates_predictor.py` (which uses `statistics_during_period`) with the newly proven local method, ensuring it successfully queries the live Home Assistant recorder online.

## Functional Requirements
1. **Live HA Recorder Integration**: The integration must adapt the proven SQLite extraction logic (or an exact HA ORM equivalent) to query the active Home Assistant recorder instance without causing `TypeError` or missing arguments online.
2. **Graceful Degradation Guarantee**: The live implementation must enforce the exact 5-day array extraction limit, applying the graceful degradation fix (closest match by error if <5 days within the 5% tolerance window) to ensure 288-interval float arrays are consistently passed to the solver.
3. **Array Synthesis**: The synthesis logic must safely pull the Amber pricing, feed-in, and load profiles for the 5 selected analog days, formatting them exactly as tested locally.
4. **TDD Coverage**: The implementation must be preceded by Test-Driven Development (TDD) tests that validate the integration logic correctly interacts with the HA environment or the HA database abstractions, incorporating the local DB tests as a baseline.

## Non-Functional Requirements
- **Stability**: The online implementation must not crash the Home Assistant event loop or the `SyntheticRatesPredictor` when executing the data extraction.
- **Performance**: The extraction must return results quickly enough to not bottleneck the plan optimization cycle.
- **Zero Regression**: The existing optimization engine logic must not be broken by this data preparation fix.

## User Scenarios
- **Scenario 1: Standard Search**: When the system needs to optimize the 48h outlook, it successfully queries the live DB, finds 5 analog days within 5% tolerance of tomorrow's PV forecast, and returns perfect 288-element float arrays.
- **Scenario 2: Sparse History**: When the system queries for a target kWh but only 1 day exists within the 5% window, it automatically defaults to the top 5 closest matches by error, completely avoiding sparsity crashes in the solver.

## Success Criteria
- The Synthetic Outlook beta panel renders successfully on the live HA instance without throwing tracebacks or missing array lengths.
- The `pytest` suite covers the new HA integration layer of the extraction method, maintaining 100% pass rates.
- The 5-day degradation bug is permanently fixed in production code.

## Assumptions & Boundaries
- The Home Assistant instance uses the standard SQLite recorder database.
- The fix only applies to the data preparation (`rates_predictor.py`), not the underlying FSM solver algorithm.
