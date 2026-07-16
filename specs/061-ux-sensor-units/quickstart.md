# Quickstart: UX Sensor Units

This feature automatically normalizes Watts and Watt-hours to Kilowatts and Kilowatt-hours.

## Configuration

When configuring the integration, users will now see detailed descriptions under each sensor field:
- **Power Sensors** (e.g. Solar, Grid, Load) will explicitly state they require an instantaneous rate (W or kW).
- **Energy Sensors** (e.g. Solar Today) will explicitly state they require an accumulated amount (Wh or kWh).

No special configuration is required to enable unit scaling. The integration automatically reads the `unit_of_measurement` of the selected sensors. If you select a Solar sensor that reports in `W`, the integration will divide its values by 1000 seamlessly in the background.
