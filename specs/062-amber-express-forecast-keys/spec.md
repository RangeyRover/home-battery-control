# Feature Specification: Amber Express Forecast Attribute Resilience

## User Scenarios & Testing

### User Scenario 1: Amber Express Entity Using `detailedForecast`
- **Given**: An Amber Express import or export price sensor with state attributes containing `detailedForecast` (camelCase) instead of `forecasts`.
- **When**: House Battery Control updates tariff rates.
- **Then**: `RatesManager` detects the `detailedForecast` attribute and parses all rate intervals without throwing warnings or failing.

### User Scenario 2: Amber Express Entity Using `detailed_forecast`
- **Given**: An Amber Express sensor with state attributes containing `detailed_forecast` (snake_case).
- **When**: House Battery Control updates tariff rates.
- **Then**: `RatesManager` falls back to `detailed_forecast` and parses the rate intervals successfully.

### User Scenario 3: Amber Express Entity Using `duration` Attribute Without `end_time`
- **Given**: Rate intervals within the Amber Express attribute list that specify `start_time` and `duration` (e.g. 5 or 30 minutes) but omit `end_time`.
- **When**: Rates are parsed by `RatesManager`.
- **Then**: `end_time` is automatically computed as `start_time + duration`.

---

## Functional Requirements

- **FR-001**: `RatesManager._parse_amber_express_entity` MUST search for detailed forecast data across attribute names in the following priority order:
  1. `detailedForecast`
  2. `detailed_forecast`
  3. `forecasts`
  4. `forecast`
  5. `future_prices`
  6. `variable_intervals`

- **FR-002**: For each item in the raw forecast array:
  - If `start_time` is present and `end_time` is missing, `end_time` MUST be calculated using `start_time + timedelta(minutes=duration)`.
  - Price MUST be extracted from `advanced_price_predicted.predicted` (or `advanced_price_predicted.high` depending on renewables threshold) if present, falling back to `per_kwh`, `perKwh`, or `value`.

- **FR-003**: If no valid array is found in any candidate attribute key, a descriptive warning log MUST be emitted, and the manager MUST return an empty list gracefully without crashing.

- **FR-004**: Unit tests MUST cover all candidate attribute key variations (`detailedForecast`, `detailed_forecast`, `forecasts`, `forecast`), missing `end_time` with `duration`, and mixed 5-min/30-min duration intervals.

---

## Success Criteria

- 100% of Amber Express entities containing `detailedForecast`, `detailed_forecast`, `forecasts`, or `forecast` are successfully parsed into valid 5-minute tick rate intervals.
- Zero rate parsing crashes or FSM solver failures due to missing `forecasts` attribute key in Amber Express mode.
- All unit tests pass cleanly with 100% coverage on `_parse_amber_express_entity`.
