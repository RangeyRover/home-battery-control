# Data Model: UX Sensor Units

No new database tables or persistent state entities are introduced in this feature.

## Updated Entity Behaviors

### Home Assistant Sensor States
When reading sensors via `hass.states.get(entity_id)`, the integration now inspects `state.attributes.get("unit_of_measurement")`:
- If `"W"`, the value is converted to `kW` (`value / 1000.0`).
- If `"Wh"`, the value is converted to `kWh` (`value / 1000.0`).
- Otherwise, the value is returned as-is (assumed `kW` or `kWh` based on the sensor context).
