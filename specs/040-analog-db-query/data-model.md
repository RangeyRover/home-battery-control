# Data Model: Analog DB Query

## Entities

### `AnalogDay`
Data class representing a matched historical day.
- `date`: `datetime` (The midnight starting point of the historical day)
- `pv_yield`: `float` (The solar generation total for that day)
- `import_pricing_curve`: `list[float]` (Array of 288 floats, 5-minute intervals)
- `export_pricing_curve`: `list[float]` (Array of 288 floats)
- `load_curve`: `list[float]` (Array of 288 floats)

### `SyntheticRatesPredictor`
- Stores `last_analog_days: list[AnalogDay]`
- Computes `synthesized_import_pricing_curve: list[float]`
- Computes `synthesized_export_pricing_curve: list[float]`
- Computes `synthesized_load_curve: list[float]`

## Validation Rules
- All curves must be strictly length 288.
- If data is missing for a time period, forward-fill the last known state. If no prior state exists, assume `0.0`.
