# Research: UX Sensor Units

## 1. Unit Scaling in Home Assistant
- **Decision**: Read the `unit_of_measurement` attribute from the state object.
- **Rationale**: Home Assistant sensor states are always strings (e.g. `"3000"`). The unit is stored in `state.attributes.get("unit_of_measurement")`. By parsing this attribute in `coordinator.py`'s `_get_sensor_value` method, we can robustly detect if a conversion is necessary. If `unit == "W"` or `unit == "Wh"`, divide by 1000. If `None` or `kW`/`kWh`, do nothing.
- **Alternatives considered**: Expecting users to create template sensors in HA to convert W to kW. Rejected because it violates the feature request to "make it as easy as possible" and "automate this".

## 2. Config Flow Texts
- **Decision**: Update `strings.json` and `translations/en.json` with detailed field descriptions.
- **Rationale**: Home Assistant config flows support `data_description` in `strings.json`. We can add descriptions under each config key to explain Power vs Energy.
- **Alternatives considered**: Using `vol.Optional(..., description=...)` in python. Rejected because HA recommends using `strings.json` for all localization and UI text.
