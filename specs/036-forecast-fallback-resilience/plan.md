# Implementation Plan: Forecast Fallback Resilience (BUG-036)

**Branch**: `036-forecast-fallback-resilience` | **Date**: 2026-04-17 | **Spec**: [spec.md](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/specs/036-forecast-fallback-resilience/spec.md)  
**Input**: Feature specification from `/specs/036-forecast-fallback-resilience/spec.md`

## Summary

The `RatesManager` is wired to parse the **general forecast entities** using the Amber Express parser when `use_amber_express=True`. The actual Amber Express entities (configured in `current_import_price_entity` / `current_export_price_entity`) are only used for row-0 instantaneous price override, not the 24-hour forecast. This results in empty rates, empty plan tables, and the express-specific pricing features (renewables weighting, advanced_price_predicted) never being applied.

**Fix strategy**: Two surgical changes — (1) rewire `RatesManager` to use express entities when available, (2) decouple plan table iteration from rates length.

## Technical Context

**Language/Version**: Python 3.12+ (Home Assistant environment)  
**Primary Dependencies**: homeassistant, scipy, numpy  
**Storage**: HA Store (`.storage/house_battery_control.cost_data`)  
**Testing**: pytest (216 tests baseline)  
**Target Platform**: Home Assistant custom integration  
**Constraints**: Must not break existing users who don't use Amber Express

## Constitution Check

No constitution file found. Proceeding with standard engineering principles:
- ✅ No new dependencies
- ✅ No new files required
- ✅ Backward compatible
- ✅ Changes confined to 2 existing source files + tests

## Project Structure

### Files Modified

```text
custom_components/house_battery_control/
├── coordinator.py          # MODIFY: RatesManager wiring + plan table iteration
├── rates.py                # MODIFY: Accept fallback entity IDs
└── translations/en.json    # MODIFY: Clarify UI labels

tests/
├── test_coordinator.py     # MODIFY: Add wiring + plan table tests
└── test_rates.py           # MODIFY: Add fallback entity tests
```

## Detailed Design

### Change 1: RatesManager Entity Wiring (FR-001, FR-002)

**File**: `coordinator.py` (lines 110-115) and `rates.py`

**Current behaviour**:
```python
# coordinator.py
self.rates = RatesManager(
    hass,
    config.get(CONF_IMPORT_PRICE_ENTITY, ""),      # ← General Forecast
    config.get(CONF_EXPORT_PRICE_ENTITY, ""),       # ← General Forecast
    use_amber_express=config.get(CONF_USE_AMBER_EXPRESS, False),
)
```

**New behaviour**:
```python
# coordinator.py
# When Amber Express is enabled AND express entities are configured,
# use express entities as primary, general forecast as fallback.
use_express = config.get(CONF_USE_AMBER_EXPRESS, False)

if use_express:
    # Prefer the express entities if configured
    import_entity = config.get(CONF_CURRENT_IMPORT_PRICE_ENTITY) or config.get(CONF_IMPORT_PRICE_ENTITY, "")
    export_entity = config.get(CONF_CURRENT_EXPORT_PRICE_ENTITY) or config.get(CONF_EXPORT_PRICE_ENTITY, "")
else:
    import_entity = config.get(CONF_IMPORT_PRICE_ENTITY, "")
    export_entity = config.get(CONF_EXPORT_PRICE_ENTITY, "")

self.rates = RatesManager(
    hass,
    import_entity,
    export_entity,
    use_amber_express=use_express,
    fallback_import_entity_id=config.get(CONF_IMPORT_PRICE_ENTITY, "") if use_express else None,
    fallback_export_entity_id=config.get(CONF_EXPORT_PRICE_ENTITY, "") if use_express else None,
)
```

**File**: `rates.py` — `RatesManager.__init__` and `update()` method

Add fallback entity support:
```python
def __init__(self, hass, import_entity_id, export_entity_id,
             use_amber_express=False,
             fallback_import_entity_id=None,
             fallback_export_entity_id=None):
    ...
    self._fallback_import_entity_id = fallback_import_entity_id
    self._fallback_export_entity_id = fallback_export_entity_id

def update(self):
    if self._use_amber_express:
        import_rates = self._parse_amber_express_entity(self._import_entity_id, "import")
        export_rates = self._parse_amber_express_entity(self._export_entity_id, "export")
        # FR-002: Fallback to general parser if express returned empty
        if not import_rates and self._fallback_import_entity_id:
            _LOGGER.warning("Amber Express import empty, falling back to general forecast")
            import_rates = self._parse_entity(self._fallback_import_entity_id, "import")
        if not export_rates and self._fallback_export_entity_id:
            _LOGGER.warning("Amber Express export empty, falling back to general forecast")
            export_rates = self._parse_entity(self._fallback_export_entity_id, "export")
    else:
        import_rates = self._parse_entity(self._import_entity_id, "import")
        export_rates = self._parse_entity(self._export_entity_id, "export")
    ...
```

**Impact**: Express entities become the primary source for 24h forecast. General forecast entities serve as fallback. Row-0 instantaneous price logic (`CONF_CURRENT_IMPORT_PRICE_ENTITY` in coordinator lines 602-612) continues to work because the express entities expose both instantaneous state AND `forecasts` arrays.

### Change 2: Plan Table Decoupling (FR-003)

**File**: `coordinator.py` — `_build_diagnostic_plan_table()` (line 290)

**Current behaviour**:
```python
for idx, rate in enumerate(rates):  # Iterates over rates — empty rates = empty table
```

**New behaviour**:
```python
# Use the longer of rates or future_plan as the iteration driver
plan_length = max(len(rates), len(future_plan))
for idx in range(plan_length):
    if idx < len(rates):
        rate = rates[idx]
        start = rate["start"]
        end = rate.get("end", start)
    elif future_plan and idx < len(future_plan):
        # Synthesize timestamp from solver step index
        start = start_ref + timedelta(minutes=5 * idx)
        end = start + timedelta(minutes=5)
        rate = {"start": start, "end": end, "import_price": 0.0, "export_price": 0.0}
    else:
        break
```

Where `start_ref` is derived from the first rate's start time (if available) or `dt_util.now()`.

**Impact**: Plan table always renders the full solver output even when rates are empty.

### Change 3: UI Label Clarification (FR-006)

**File**: `translations/en.json` (lines 34-35, 99-100)

```diff
- "current_import_price_entity": "Import Price Entity (e.g. Amber Express General Price Detailed) [Optional - Only if Amber Express used]",
- "current_export_price_entity": "Export Price Entity (e.g. Amber Express Feed-in Price Detailed) [Optional - Only if Amber Express used]",
+ "current_import_price_entity": "Amber Express Import Entity (Primary 24h source when Express enabled)",
+ "current_export_price_entity": "Amber Express Export Entity (Primary 24h source when Express enabled)",
```

### Change 4: Instantaneous Price Logic Preservation

**File**: `coordinator.py` lines 602-612

The existing row-0 override logic uses `CONF_CURRENT_IMPORT_PRICE_ENTITY` to get the instantaneous price from the express entity's `state` value. After Change 1, the same entity is also used by `RatesManager` for the forecast. This is correct — express entities expose both `state` (instantaneous) and `attributes.forecasts` (24h timeline). No change needed here, but a test must verify both uses work simultaneously.

## Test Plan

### New Tests

1. **`test_rates_amber_express_uses_correct_entities`** — Assert that when `use_amber_express=True` and express entities are configured, `RatesManager` reads from express entities, not general forecast.

2. **`test_rates_amber_express_fallback_to_general`** — Assert that when express entities return empty data, `RatesManager` falls back to general forecast parser.

3. **`test_rates_amber_express_both_unavailable`** — Assert that when both express and general entities are unavailable, `RatesManager` returns empty rates without raising.

4. **`test_plan_table_renders_with_empty_rates`** — Assert that `_build_diagnostic_plan_table` produces 288 rows when `rates=[]` but `future_plan` has 288 entries.

5. **`test_plan_table_renders_with_partial_rates`** — Assert that when rates has fewer intervals than future_plan, the table extends to cover all solver steps.

### Regression

- Full 216-test suite must pass.
- Existing `test_rates.py` tests for non-express mode must be unaffected.

## Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Express entity `state` now used for both instantaneous AND forecast | Low | Express entities inherently provide both — tested explicitly |
| Fallback to general parser introduces unexpected pricing | Low | Logged at WARNING, user can see degraded state |
| Plan table timestamp synthesis inaccurate without rates | Medium | Use `dt_util.now()` as reference, 5-min step increment |
| Existing non-express users affected | Low | Changes gated behind `use_amber_express=True` |
