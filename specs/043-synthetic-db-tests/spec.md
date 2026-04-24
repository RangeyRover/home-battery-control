# Feature Specification: Synthetic DB Tests

**Feature Name:** Synthetic DB Tests  
**Branch:** `043-synthetic-db-tests`  
**Status:** DRAFT

## Goal
Establish a robust, standalone test suite to validate the synthetic analog day extraction against a local SQLite database copy before attempting deployment to the live Home Assistant instance. The suite will definitively prove that the system can query the 950MB Home Assistant database, identify the 5 closest analog days based on daily solar generation, and correctly extract and synthesize the resulting pricing, export, and load curves using varying target input amounts (30, 28, 26, 24, 22, 20, 18, 16, and 14 kWh).

## Context & User Value
We are experiencing failures in the beta panel related to the database queries for the 48-hour synthetic outlook. Because the online Home Assistant instance is harder to debug and has performance constraints, we need absolute certainty that the underlying SQL query logic and the Python array synthesis correctly identifies and shapes the output data. 
By wrapping this logic in a comprehensive parameterized test suite executing against a local replica of the `home-assistant_v2.db` database, we can iterate rapidly, prove the mathematical correctness of our extraction algorithm, and verify that it gracefully handles various target generation amounts without failure. This prevents live instance crashes and ensures the resulting UI panel will render meaningful data.

## Functional Requirements
1. **Local Database Connection:** The test suite must be capable of establishing an asynchronous or synchronous read-only connection to a local copy of `home-assistant_v2.db`.
2. **Target Parameterization:** The test suite must run the analog day extraction algorithm against a parameterized list of target daily solar generation amounts: 30, 28, 26, 24, 22, 20, 18, 16, and 14 kWh.
3. **Entity Verification:** The suite must correctly identify and pull state data for the necessary sensor entities (`sensor.solcast_pv_forecast_forecast_today`, `sensor.powerwall_solar_export`, `sensor.powerwall_load_export`, `sensor.amber_general_price`, `sensor.amber_feed_in_price`).
4. **Day Selection Accuracy:** For each target amount, the suite must successfully isolate the 5 days from the database history whose total solar generation most closely matches the target.
5. **Data Synthesis Validation:** The suite must successfully aggregate the 5 analog days into single 288-interval arrays (5-minute resolution) for pricing, export, and load curves.
6. **Tolerance Handling:** The selection algorithm must be verified to correctly apply a 5% tolerance bounds check (as discussed previously) to isolate days.
7. **Output Stability:** The output arrays must not contain nulls, gaps, or type errors that would break the frontend graph.

## User Scenarios & Acceptance Criteria

### Scenario 1: Executing the Parametrized Test Suite
**Given** a local, populated Home Assistant database replica exists in the expected directory,
**When** the test suite is executed,
**Then** it should iterate through all specified target kWh values (14-30), successfully locate analog days for each (where historical data permits), and complete without raising any SQL execution errors or Python exceptions.

### Scenario 2: Validating Data Shape
**Given** the test suite has extracted the analog days for a specific target (e.g., 24 kWh),
**When** the synthesis phase completes,
**Then** it must output three distinct arrays (pricing, export, load) that each contain exactly 288 floating-point values representing the synthetic 24-hour period.

### Scenario 3: Missing or Insufficient Data Graceful Degradation
**Given** a target value where 5 distinct days within the 5% tolerance cannot be found in the historical data,
**When** the test runs,
**Then** it should gracefully fall back to selecting the closest available days without crashing, or return a clearly defined fallback pattern.

## Success Criteria
- **100% Test Pass Rate:** The new test script runs completely against the local database copy without any failures.
- **Data Integrity:** All synthesized arrays are verified to be exactly length 288, containing only valid numerical values.
- **Confidence to Deploy:** The test output proves conclusively that the `homeassistant.helpers.recorder` logic (or raw SQLite query equivalent) correctly builds the data structures needed for the synthetic panel.

## Assumptions & Boundaries
- The local database replica (`home-assistant_v2.db`) is already downloaded, accessible, and contains sufficient historical data to cover the tested ranges.
- This specification covers the creation and validation of the tests and the query logic. Deployment of the fixed logic to the live HA instance will follow once these tests pass.
- The tests will run outside of the standard Home Assistant event loop context, likely requiring a mocked or standalone database engine (like raw `aiosqlite` or `sqlite3`) to simulate the recorder component.

## Needs Clarification
- None.
