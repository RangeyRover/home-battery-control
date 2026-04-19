# Phase 0 Research: Analog DB Query

## How to Query the Home Assistant Recorder DB for Historical States
To query history without locking the event loop:
1. `from homeassistant.components.recorder import history`
2. `states_dict = await hass.async_add_executor_job(history.get_significant_states, hass, start_date, end_date, [entity_id])`
3. Then iterate over `states_dict[entity_id]` to extract the timeline.

## Data Normalization to 288 Steps (5-min intervals)
Since we need exactly 288 steps for 24 hours:
- Use `dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)` for midnight alignment on the historical date.
- Create 288 intervals.
- Perform a forward-fill linear interpolation (as used in `historical_analyzer.py`) or simple step-hold logic for the price states, since prices generally stay static until they change abruptly.

## Extracting all three metrics
The clarification indicated we must extract:
1. Import Price (`price_entity_id`)
2. Export Price (`export_price_entity_id`)
3. Load Profile (`load_entity_id`)

All three must be normalized into 288-step float arrays.
