# House Battery Control

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A deterministic Home Assistant custom integration for optimising Tesla Powerwall battery usage. Uses a Linear Programming solver to minimise daily electricity costs based on real-time Amber Electric spot pricing, Solcast solar forecasts, and historical load patterns.

## What It Does

Every 5 minutes, HBC collects your current energy tariffs, solar production forecast, and household load history. It feeds this data into an LP solver that calculates the mathematically optimal battery charge/discharge schedule for the next 24 hours, then sends the appropriate command to your Powerwall.

![24-Hour Plan — the solver's optimal schedule with pricing, state, SoC, and cost projections](docs/images/plan-panel.png)

## Prerequisites

| Requirement | Purpose | Integration |
|---|---|---|
| **Home Assistant** 2024.1+ | Platform | — |
| **HACS** | Installation | [hacs.xyz](https://hacs.xyz) |
| **Amber Electric** | 5-minute spot pricing | [Amber Electric](https://www.home-assistant.io/integrations/amber/) |
| **Solcast** | Solar production forecast | [Solcast HACS](https://github.com/oziee/ha-solcast-solar) |
| **Tesla Powerwall** | Battery control | [Teslemetry](https://github.com/Teslemetry/ha-teslemetry) or similar |
| **Weather** | Temperature forecast (optional) | Any HA weather entity |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the **⋮** menu → **Custom repositories**
3. Add: `https://github.com/RangeyRover/home-battery-control` (Category: **Integration**)
4. Search for **House Battery Control** and click **Download**
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration → House Battery Control**

### Manual

```bash
cp -r custom_components/house_battery_control /config/custom_components/
ha core restart
```

## Configuration

The integration uses a 3-step config flow. For full details on every field, see [docs/configuration.md](docs/configuration.md).

| Step | What You Configure |
|---|---|
| **1. Telemetry** | Battery SoC, Battery Power, Solar Power, Grid Power sensors (with inversion options) |
| **2. Energy & Metrics** | Cumulative energy sensors, temperature thresholds, battery specs, tariff & weather entities |
| **3. Control** | Charge/discharge scripts, panel visibility toggle |

You can also configure via YAML import on Step 1.

## Verifying It Works

After configuration:

1. **Sidebar** — Look for the **HBC** entry (battery icon) in the sidebar
2. **Panel** — Click it to see the power flow diagram and system status
3. **Sensors** — Check **Settings → Devices → House Battery Control** for `sensor.hbc_state` and `sensor.hbc_projected_cost`
4. **API** — Visit `/hbc/api/status` (requires admin auth) for full diagnostic JSON

## Documentation

| Document | Description |
|---|---|
| [Configuration Reference](docs/configuration.md) | Every config option explained |
| [How It Works](docs/how-it-works.md) | Data pipeline, solver objectives, I/O detail |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes |
| [Architecture](docs/architecture.md) | Module map and contributor guide |

## Development

```bash
pip install -r requirements_test.txt
python -m pytest tests/ -v      # 191 tests
ruff check custom_components/ tests/
```

## License

[MIT](LICENSE)
