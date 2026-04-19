# Implementation Plan: Synthetic DB Tests

This document outlines the technical implementation for the local database tests requested in the `043-synthetic-db-tests` specification.

## User Review Required

> [!IMPORTANT]
> Since the `home-assistant_v2.db` database is 950MB and not checked into version control, the test suite will be configured to look for the database file at a specific path (e.g. `tests/test_data/home-assistant_v2.db`) or via an environment variable `HBC_TEST_DB_PATH`. You will need to place the database file in that location for the tests to run successfully.

## Open Questions

- Where is the `home-assistant_v2.db` file located on your local machine so we can accurately point the test script to it?

## Proposed Changes

We will create a standalone integration test script using `pytest` and `pytest-asyncio` that connects to the SQLite database and executes the `_run_analog_search` logic.

### 1. Extract and Refactor DB Queries (If Necessary)
To test the analog search independently from the full Home Assistant core environment, we may need to adapt `SyntheticRatesPredictor._run_analog_search` to support a generic `sqlite3` or `aiosqlite` connection interface, rather than relying strictly on the `homeassistant.helpers.recorder` which is difficult to mock.
Alternatively, we will write a raw test script `tests/test_analog_db.py` that connects directly using standard Python libraries to execute the equivalent SQL.

### 2. Test File Generation

#### [NEW] `tests/test_analog_db.py`
A comprehensive parameterized test suite validating the analog search algorithm.

- **Setup Module**: Connect to `home-assistant_v2.db` using `aiosqlite` based on an environment variable or default path.
- **Test Cases**: Parameterized across `[30, 28, 26, 24, 22, 20, 18, 16, 14]` kWh targets.
- **Validation**: 
  - Assert exactly 5 analog days are found within the 5% tolerance window.
  - Assert the synthetic pricing, export, and load arrays are exactly length 288.
  - Assert the data types are correct (lists of floats, no nulls).

## Verification Plan

### Automated Tests
Execute the new test suite directly:
```bash
pytest tests/test_analog_db.py -v
```
This will confirm all kWh targets successfully synthesize valid output arrays from the downloaded 950MB database.
