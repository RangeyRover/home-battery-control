# Research & Analysis: Amber Express Forecast Attribute Keys

## Technical Findings

1. **Attribute Name Variants**:
   - Official/Legacy Amber Express sensor attribute names include: `detailedForecast`, `detailed_forecast`, `forecasts`, `forecast`, `future_prices`, `variable_intervals`.
   - `detailedForecast` (camelCase) is used in the latest integration releases for detailed 5-minute price predictions and advanced price intervals.

2. **Duration and Time Calculation**:
   - Amber Express items provide `start_time` in ISO format (e.g. `2026-07-25T06:45:01+00:00`) and a `duration` in minutes (e.g. 5 or 30).
   - Some items specify `end_time`, while others omit it.
   - Fallback logic: `end_ts = start_ts + timedelta(minutes=duration)`. If `duration` is absent, default to 5 minutes for detailed forecast items or 30 minutes for standard forecast items.

3. **Price Field Extraction**:
   - `advanced_price_predicted`: dict containing `predicted`, `high`, `low`.
   - Renewables threshold logic:
     - `renewables >= 35.0`: use `predicted`
     - `renewables <= 25.0`: use `high`
     - `25.0 < renewables < 35.0`: linear interpolation.
   - If `advanced_price_predicted` is missing, check `per_kwh`, `perKwh`, `spot_per_kwh`, or `value`.

## Rationale
Using a fallback sequence for attribute lookup prevents integration crashes or silent empty rate array returns regardless of Amber Home Assistant integration updates or entity variations.
