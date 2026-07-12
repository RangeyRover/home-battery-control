# 060-complex-tou-config

This plan upgrades the Fixed Time-of-Use feature to support up to 10 arbitrary import and 10 export periods per day, enabling complex tariffs and Feed-in Tariffs (FiT). It implements a strict 24-hour validation rule (00:00 to 00:00) with no midnight crossing permitted per period block.

## Proposed Changes

---

### `custom_components/house_battery_control/const.py`

Define 60 new configuration keys for Import and Export periods (1 to 10 for each `start`, `end`, and `price`).
#### [MODIFY] const.py

### `custom_components/house_battery_control/config_flow.py`

Update the Fixed TOU configuration step to render the 10 predefined periods for import and 10 for export.
Implement validation logic that:
1. Ignores unused (blank) periods.
2. Sorts populated periods by start time.
3. Validates that the first period begins exactly at `00:00:00`.
4. Validates that the last period ends exactly at `00:00:00` (representing midnight of the next day).
5. Validates that each period's end time exactly matches the subsequent period's start time (no gaps, no overlaps).
#### [MODIFY] config_flow.py

### `custom_components/house_battery_control/fixed_tou.py`

Refactor `FixedTOUGenerator` to accept the parsed lists of import and export periods instead of hardcoded peak/offpeak/shoulder keys.
Update `_get_price_for_time` to search the sorted periods and return the matching price.
Add `_get_export_price_for_time` to return export pricing (instead of defaulting to 0.0).
Ensure the `generate_forecast` loop populates both `import_price` and `export_price` correctly in the returned blocks.
#### [MODIFY] fixed_tou.py

### `custom_components/house_battery_control/rates.py`

Update the `RatesManager` fallback logic for Fixed TOU to extract `export_price` from the generated forecast blocks instead of defaulting to `0.0`.
#### [MODIFY] rates.py

---

## Verification Plan (TDD)

Per the strict TDD mandate, test files will be authored and run *before* the application code is changed.

### Automated Tests
1. **Validation Tests (`tests/test_config_flow.py`)**:
   - Write tests validating successful 24-hour coverage.
   - Write tests expecting failure for gaps (e.g., missing 12:00 - 13:00).
   - Write tests expecting failure for overlaps (e.g., 12:00 - 14:00 and 13:00 - 15:00).
   - Write tests expecting failure for crossing midnight (start > end).
   - Write tests expecting failure if first period does not start at 00:00.
2. **Generator Tests (`tests/test_fixed_tou.py`)**:
   - Write tests verifying `FixedTOUGenerator` accurately builds a 48-hour forecast with varying import and export prices.
   - Test midnight wrap-around over a multi-day forecast.
   - Test the extraction of `import_price` and `export_price` properly populates the downstream arrays.

**Execution Order**:
1. Add new tests to `test_config_flow.py` and `test_fixed_tou.py`.
2. Run `pytest` to confirm they fail.
3. Implement changes in `const.py`, `config_flow.py`, `fixed_tou.py`, `rates.py`.
4. Run `pytest` to confirm they pass.
