# Data Model & Schema: Amber Express Tariff Interval Parsing

## Data Structures

### Raw Amber Express Interval Schema (Attributes)
- `detailedForecast` / `detailed_forecast` / `forecasts` / `forecast`: `list[dict]`
  - `start_time`: `str` (ISO-8601 datetime)
  - `end_time`: `str | None` (ISO-8601 datetime)
  - `duration`: `int | float | None` (minutes)
  - `renewables`: `float | None` (percentage 0-100)
  - `per_kwh` / `perKwh` / `value`: `float | None` ($/kWh)
  - `advanced_price_predicted`: `dict | None`
    - `predicted`: `float`
    - `high`: `float`
    - `low`: `float`

### Output Internal `RateInterval` Struct
- `start`: `datetime` (UTC-aware)
- `end`: `datetime` (UTC-aware)
- `price`: `float` (c/kWh or $/kWh normalized)
- `renewables`: `float | None`
- `type`: `"FORECAST"`
