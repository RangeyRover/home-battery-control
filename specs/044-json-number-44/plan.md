# Implementation Plan: Online Analog DB Method

This document outlines the technical implementation for adapting the proven local SQLite extraction logic into the live Home Assistant integration context (`rates_predictor.py`).

## Proposed Changes

We will refactor `SyntheticRatesPredictor._run_analog_search` to bypass the unstable `statistics_during_period` API entirely, resolving the `TypeError: 'NoneType' object is not iterable` crashes. Instead, we will directly query the HA Recorder's `statistics` and `statistics_meta` tables using the SQLAlchemy connection provided by HA, utilizing the raw queries proven in our local test suite.

### 1. Database Extraction via SQLAlchemy Core
Home Assistant's `recorder` component exposes a synchronous SQLAlchemy engine. We will execute our raw queries via `session.execute(text("..."))` or `engine.execute(...)`.

```python
from homeassistant.components.recorder import get_instance
from sqlalchemy import text

def _run_analog_search(self, target_kwh: float):
    engine = get_instance(self._hass).engine
    with engine.connect() as conn:
        # 1. Execute proven Solcast statistics query
        # 2. Execute proven curve extraction query
```

### 2. TDD Test Cases First
Before altering `rates_predictor.py`, we will adapt `tests/test_analog_db.py` or create a new test file `tests/test_online_analog_db.py` that utilizes a mocked `hass` with an initialized `recorder` component (via `pytest-homeassistant-custom-component` or a mocked SQLAlchemy Engine). Since setting up the full HA ORM in `pytest` for statistics tables is heavy, we will either:
- Continue using pure `sqlite3` in the tests and inject a database path into the predictor class during testing.
- OR use a Mock Engine that simulates SQLAlchemy `conn.execute()` returning lists of tuples.

### 3. Graceful Degradation Bug Fix
We will implement the exact 5-day fallback bugfix from `043-synthetic-db-tests` inside `rates_predictor.py`:
```python
if len(candidate_days) >= 5:
    # ...
else:
    sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
    top_5_days = sorted_by_error[:5]
```

## Phase Structure

1. **Phase 1: Test Integration**: Setup TDD tests mocking the `recorder` engine interface so that `_run_analog_search` can be executed under test coverage.
2. **Phase 2: Logic Transfer**: Replace `statistics_during_period` and `history.get_significant_states` with raw `sqlalchemy.text` execution in `rates_predictor.py`.
3. **Phase 3: Validation**: Ensure all parameter target variations pass perfectly.

## Verification Plan

### Automated Tests
Run the updated `pytest tests/test_rates_predictor.py -v` suite to ensure the new method operates reliably against the test database schema.

### Manual Verification
The new integration will be deployed to the beta HA instance to verify the Synthetic Outlook panel loads correctly without tracebacks.
