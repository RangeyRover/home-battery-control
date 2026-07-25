# Implementation Plan: Amber Express Forecast Attribute Resilience

Support Amber Express detailed forecast attributes across various attribute names (`detailedForecast`, `detailed_forecast`, `forecasts`, `forecast`, `future_prices`, `variable_intervals`) and handle missing `end_time` by using `duration`.

## Proposed Changes

### Core Component (`rates.py`)

#### [MODIFY] [rates.py](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/custom_components/house_battery_control/rates.py)

- Update `_parse_amber_express_entity` to iterate over candidate attribute names:
  `detailedForecast`, `detailed_forecast`, `forecasts`, `forecast`, `future_prices`, `variable_intervals`.
- Handle `end_time` calculation: if `end_time` is missing but `duration` is provided, calculate `end_ts = start_ts + timedelta(minutes=float(duration))`.
- Extract fallback price if `advanced_price_predicted` is not present: `per_kwh`, `perKwh`, `value`.

### Unit Tests (`test_rates.py`)

#### [MODIFY] [test_rates.py](file:///C:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/tests/test_rates.py)

- Add unit test cases for:
  - Amber Express sensor with `detailedForecast` (camelCase)
  - Amber Express sensor with `detailed_forecast` (snake_case)
  - Amber Express sensor omitting `end_time` but providing `duration`
  - Amber Express fallback when `advanced_price_predicted` is missing.

## Verification Plan

### Automated Tests
- Run `pytest tests/test_rates.py -v`
