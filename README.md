# House Battery Control

A deterministic Home Assistant custom integration for controlling Tesla Powerwall batteries using a Finite State Machine (FSM). Replaces complex ML approaches with rule-based logic for reliable, low-resource operation.

## Features

- **Deterministic FSM** — 6 states: IDLE, CHARGE_GRID, CHARGE_SOLAR, DISCHARGE_HOME, DISCHARGE_GRID, PRESERVE
- **5-minute cadence** — Aligned with Amber Electric pricing intervals
- **Temperature-sensitive load prediction** — Adjusts forecasts based on weather
- **Deduplicating executor** — Only sends commands when state changes
- **Web dashboard** — Power flow diagram, 24h plan table, JSON API
- **3-step config flow** — Telemetry → Energy & Metrics → Control Services

## System

- 2× Tesla Powerwall 2 (27 kWh usable)
- 4 kW solar array
- Amber Electric (5-min spot pricing)
- Solcast solar forecasting

## Installation

### HACS (Recommended)
1. Add this repository as a custom repository in HACS
2. Install "House Battery Control"
3. Restart Home Assistant
4. Add integration: **Settings → Devices → Add Integration → House Battery Control**

### Manual
```bash
# Copy to your HA config directory
cp -r custom_components/house_battery_control /config/custom_components/

# Restart HA
ha core restart
```

## Dashboard

After setup, browse to `http://<ha-ip>:8123/hbc` for:
- **Power flow diagram** — Real-time SVG showing Grid ↔ Battery ↔ Solar ↔ House
- **24-hour plan table** — Price, FSM state, forecasts, costs per 5-min interval
- **JSON API** — `/hbc/api/status` and `/hbc/api/ping`

## Configuration

The integration uses a 3-step config flow:

| Step | Entities |
| :--- | :--- |
| Telemetry | Battery SoC, Battery Power, Solar Power, Grid Power (with inversion options) |
| Energy & Metrics | Load/Import/Export today, temperature thresholds, battery capacity, tariff & weather entities |
| Control | Grid charging switch, operation mode select |

## Development

```bash
# Install dependencies
pip install -r requirements_test.txt

# Run tests
python -m pytest tests/ -q

# Run linter
ruff check custom_components/ tests/
```

## License

MIT
