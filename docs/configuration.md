# Configuration Reference

This document covers every configuration option available in the House Battery Control integration.

## Initial Setup (Config Flow)

After installing HBC, go to **Settings → Devices & Services → Add Integration → House Battery Control**.

You can choose between **Manual** configuration (3-step wizard) or **YAML import** (paste a YAML block with all settings).

---

## Step 1: Telemetry (Power Sensors)

These are the real-time power sensors HBC reads every 5 minutes.

| Key | Label | Type | Required | Notes |
|---|---|---|---|---|
| `battery_soc_entity` | Battery SoC | `sensor` | ✅ | Current battery state of charge (%). Must report 0–100. |
| `battery_power_entity` | Battery Power | `sensor` | ✅ | Current battery charge/discharge power (kW). |
| `battery_power_invert` | Invert Battery Power | `boolean` | ❌ | Enable if your sensor reports charging as negative. Default: off. |
| `solar_entity` | Solar Power | `sensor` | ✅ | Current solar production (kW). |
| `grid_entity` | Grid Power | `sensor` | ✅ | Current grid import/export power (kW). |
| `grid_power_invert` | Invert Grid Power | `boolean` | ❌ | Enable if your sensor reports import as negative. Default: off. |
| `load_power_entity` | Load Power | `sensor` | ❌ | Current house load (kW). Optional — can be derived from other sensors. |

### When to Use Inversion

Different inverter brands report power direction differently:

- **Tesla Gateway**: Battery power is positive when discharging → **no inversion needed**
- **Some inverters**: Battery power is positive when charging → **enable inversion**
- **Grid sensors**: Positive = import is the HA convention, but some sensors use positive = export → **enable inversion** if your grid sensor is backwards

---

## Step 2: Energy & Metrics

Cumulative energy sensors, forecasting sources, and battery specifications.

### Cumulative Energy Sensors

| Key | Label | Type | Required | Notes |
|---|---|---|---|---|
| `load_today_entity` | Load Today | `sensor` | ❌ | Cumulative household energy today (kWh). Used for load prediction. |
| `import_today_entity` | Import Today | `sensor` | ❌ | Cumulative grid import today (kWh). Displayed on dashboard. |
| `export_today_entity` | Export Today | `sensor` | ❌ | Cumulative grid export today (kWh). Displayed on dashboard. |

### Temperature Calibration

These adjust the load forecast based on temperature. HBC compares the **forecast temperature** against the **historical average temperature** for each time slot to calculate how much HVAC load to add or remove from the prediction.

The adjustment uses an **excess-based formula**: only the portion of temperature that crosses a threshold contributes to the adjustment. For example, if history was 30°C and the high threshold is 25°C, 5°C of cooling load was baked into the historical average. If today's forecast is 22°C (no cooling needed), the prediction is reduced by `5 × sensitivity` kW.

| Key | Label | Default | Notes |
|---|---|---|---|
| `load_high_temp_sensitivity` | High Temp Sensitivity | `0.0` | kW adjustment per °C of cooling excess above threshold |
| `load_low_temp_sensitivity` | Low Temp Sensitivity | `0.0` | kW adjustment per °C of heating excess below threshold |
| `load_high_temp_threshold` | High Temp Threshold | `25.0` | °C above which cooling load is expected |
| `load_low_temp_threshold` | Low Temp Threshold | `15.0` | °C below which heating load is expected |

### Battery Specifications

| Key | Label | Default | Notes |
|---|---|---|---|
| `battery_capacity` | Battery Capacity | `27.0` | Total usable capacity in kWh (2× Powerwall 2 = 27 kWh) |
| `battery_rate_max` | Max Charge/Discharge Rate | `6.3` | Maximum charge/discharge rate in kW |
| `inverter_limit` | Inverter Limit | `10.0` | Maximum inverter throughput in kW |
| `round_trip_efficiency` | Round-Trip Efficiency | `0.90` | Charging/discharging efficiency (0.0–1.0). Solver uses √(RTE) per conversion. |
| `reserve_soc` | Reserve SoC | `0.0` | Minimum battery SoC (%) the solver will maintain |
| `load_cache_ttl_minutes` | Load Cache TTL | `360` | How long to cache the 5-day load history (minutes, 5–1440). Default 360 = 6 hours. |

### Pricing & Forecast Sources

| Key | Label | Default | Notes |
|---|---|---|---|
| `import_price_entity` | Import Price Forecast | — | Amber Electric import price sensor. Reports c/kWh with `forecast` attribute. |
| `export_price_entity` | Export Price Forecast | — | Amber Electric export/feed-in price sensor. Reports c/kWh with `forecast` attribute. |
| `current_import_price_entity` | Current Import Price | — | **Optional:** Sensor tracking Amber's instantaneous/live import price. Decouples step 0 from forecast arrays. |
| `current_export_price_entity` | Current Export Price | — | **Optional:** Sensor tracking Amber's instantaneous/live export price. |
| `weather_entity` | Weather Entity | — | Any HA weather entity providing temperature forecasts. |
| `solcast_today_entity` | Solcast Today | `sensor.solcast_pv_forecast_today` | Solcast PV forecast for today. |
| `solcast_tomorrow_entity` | Solcast Tomorrow | `sensor.solcast_pv_forecast_tomorrow` | Solcast PV forecast for tomorrow. |

---

## Step 3: Control Services

Scripts that HBC calls to control the Powerwall. Leave blank for observation/debug mode (HBC calculates but doesn't act).

| Key | Label | Notes |
|---|---|---|
| `script_charge` | Script: Charge from Grid | Called when FSM enters `CHARGE_GRID` state |
| `script_charge_stop` | Script: Stop Charging | Called when FSM exits charging states |
| `script_discharge` | Script: Discharge to Grid | Called when FSM enters `DISCHARGE_GRID` state |
| `script_discharge_stop` | Script: Stop Discharging | Called when FSM exits discharge states |
| `allow_charge_entity` | Allow Grid Charge Entity | Optional Teslemetry toggle entity that enables/disables grid charging. |
| `allow_export_entity` | Allow Export Entity | Optional Teslemetry toggle entity that enables/disables grid export. |
| `observation_mode` | Observation Mode | Boolean. When ON, HBC calculates the optimal plan but does NOT send commands to the Powerwall. Useful for dry-run testing. |
| `no_import_periods` | No-Import Periods | String format periods (e.g. `15:00-21:00`) restricting LP arbitrage charging. |
| `panel_admin_only` | Panel Visible to Admins Only | Toggle: ON = sidebar entry visible to admin users only (default). OFF = visible to all users. |

---

## Options Flow (Changing Settings After Install)

To change any setting after initial configuration:

1. Go to **Settings → Devices & Services**
2. Find **House Battery Control** and click **Configure** (gear icon)
3. Select the category to edit: **Telemetry**, **Energy & Metrics**, or **Control Services**
4. Make changes and click **Submit**
5. The integration will reload with the new settings

> **Note**: Some changes (like `panel_admin_only`) require an integration reload or HA restart to take effect.
