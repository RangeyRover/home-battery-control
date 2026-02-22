# System Requirements: House Battery Control System

## 1. Introduction
This document defines the requirements for a **Home Assistant Custom Integration** designed to control a residential battery system (2x Tesla Powerwall 2, 27kWh total) and solar array (4kW). The system replaces greedy, point-in-time rule cascades with a **Dynamic Programming (DP) mathematical tree search** to determine the absolute cheapest 24-hour battery schedule, ensuring reliability and solving complex edge cases like Negative Export Traps.

## 6. Testing Methodology
Because the DP engine utilizes a multi-hour mathematical profile strategy, atomic point-in-time testing (e.g. "assert CHARGE_GRID at t=0") is fundamentally flawed.
1. **Assert DP Policy Trees:** Ensure the DP solver successfully builds a multi-step `policy` array indicating the intended SoC at each chronological block. Test assertions must traverse this policy array.
2. **Negative Export Trap Validation:** Explicitly craft tests where cheap charging is available at `t=0`, but a massive solar negative-export penalty exists in the future. The test must guarantee the DP solver sets a policy of `IDLE` (or discharge) at `t=0` to reserve physical battery space for the future trap.
3. **Solver Validations:** The DP testing suite must guarantee that "doing nothing" (Idling) is mathematically permitted during solar-excess evaluation blocks, preventing the tree from being blinded to the strategy of ignoring solar.

## 2. Functional Requirements

### 2.1. Core Logic (State Machine)
The system must operationally control the battery based on a Finite State Machine (FSM). 

#### Logical States:
1.  **IDLE**: Battery is standby.
2.  **CHARGE_GRID**: Force charging from the grid (e.g., negative prices, cheap window).
3.  **CHARGE_SOLAR**: Charge only from excess solar.
4.  **DISCHARGE_HOME**: Support household load (self-consumption).
5.  **PRESERVE**: Maintenance of charge level (hold for upcoming peak).

*Note: While the FSM calculates these logical states, the physical execution is mapped to strictly four action scripts (see 3.6).*

### 2.2. Web Interface (Custom Panel)
The web interface must be implemented as an HA **custom panel** (`panel_custom`):
-   **Technology**: LitElement web component.
-   **Data Source**: The panel fetches live data from `/hbc/api/status`.
-   **Views**: Dashboard (Power flow SVG + status) and Plan (24-hour look-ahead).

#### 2.2.1. Plan Table Data Interpolation
*Note: The Plan Table (accessed via `/hbc/plan`) is maintained strictly for diagnostic purposes and will not be a part of the final production application. However, its contents must structurally and numerically match the exact internal FSM plan array from which all battery calculations are derived.*

The internal Plan Table utilizes the **Amber Grid Tariff** array as its backbone. Because the tariff array generates mixed temporal intervals (e.g. initial 5-minute blocks changing to 30-minute blocks), all forecast data must be structurally mapped by **timestamp** rather than sequential index.
- **PV Forecast (Solcast)**: Must be proportionally interpolated. If the estimate is an hourly sum, it must be divided to accurately reflect the row's physical duration (e.g., dividing by 12 for a 5-min row).
- **Load Forecast**: Must be mapped by finding all forecast segments whose timestamps fall within the row's start and end times, outputting the average of the matched intervals.
- **Weather Forecast**: Must be mapped to the closest matching record using the nearest-neighbor temporal difference.

### 2.3. Web API Endpoints
-   **Status API** (`/hbc/api/status`): JSON with operational data + diagnostics.
-   **Config Export API** (`/hbc/api/config-yaml`): Returns the integration configuration as a valid YAML string. Must handle `MappingProxyType` correctly.
-   **Health Check** (`/hbc/api/ping`): `/hbc/api/ping`
-   **Historic Load API** (`/hbc/api/load-history`): JSON providing raw historic data and derived 5-minute power samples used for FSM alignment.

### 2.4. API Diagnostics (`/hbc/api/status`)
The status API must return the **full coordinator data** for debugging:
-   **Sensor Diagnostics**: For each configured entity (including Solcast and Control scripts), report `{entity_id, state, available, attributes}`.
-   **Coordinator Data Passthrough**: ALL coordinator fields.

## 3. Data Interface Specifications

### 3.1. Grid Tariff (Amber Electric Schema)
Amber Electric provides separate import and export price forecasts.
-   The current price is the entity's `state`. 
-   **CRITICAL**: The forecast is found specifically in `attributes.forecast` (must check this exact key, adhering to the Amber schema).

Each interval features:
```json
[
  {
    "periodType": "ACTUAL",
    "periodStart": "2025-02-20T12:00:00Z",
    "periodEnd": "2025-02-20T12:05:00Z",
    "perKwh": 25.5,
    "spotPerKwh": 15.2,
    "descriptor": "general"
  }
]
```

### 3.2. Solar Forecast (Solcast HA Integration)
Reads forecast data from the HA Solcast integration (`sensor.solcast_pv_forecast_today` and `tomorrow`). 

### 3.3. Weather Forecast (Home Assistant Service)
Uses the modern HA `weather.get_forecasts` service (HA 2023.9+).

### 3.4. Historical Load Data
The Load Predictor uses historical data to forecast the upcoming 24 hours.
- It pulls data for the **past 5 days** to establish the base load prediction. 
- **Internal History API**: The system MUST fetch historical data via the internal Home Assistant history API (`homeassistant.components.history.get_significant_states`).
- **REST Equivalent Formatting**: The internal states MUST be strictly serialized into a JSON-equivalent list of lists of dictionaries matching the exact REST API structure. The payload MUST match the following schema:
  ```json
  [
    [
      {
        "entity_id": "sensor.example_energy_kwh",
        "state": "51.4725",
        "last_changed": "2026-02-16T06:07:41+00:00",
        "last_updated": "2026-02-16T06:07:41+00:00",
        "attributes": {
          "state_class": "total_increasing",
          "unit_of_measurement": "kWh",
          "device_class": "energy"
        }
      }
    ]
  ]
  ```
- **Data Period**: The fetched period should start exactly 5 days ago and end at the exact current prediction start time.
- **Interpolation & Anomaly Handling**: When converting raw history points into the 5-minute array, the predictor MUST:
   1. Filter out non-numerical states.
   2. Sort points sequentially by timestamp.
   3. Use **Linear Interpolation** to calculate the exact state value at any specific 5-minute boundary between two raw data points.
   4. Detect **midnight resets** (when `delta < 0`). Instead of zeroing it out, the system must assume the usage during this gap was identical to the *previous* 5-minute interval's valid usage.

### 3.4. FSM Internal State
Context object containing SoC, solar production, load power, grid voltage, price, and 24h forecasts.

### 3.5. Comprehensive I/O Mapping & Configurability
All sensor inputs are selectable via the Home Assistant UI (Config Flow). 

#### 3.6. Control Entities (Writable — Optional)
The integration maps logical FSM states to four explicit Home Assistant script entities. All are optional. If not configured, the system runs in observation mode.
- **Charge Battery Script**: Called to initiate forced charging from the grid.
- **Charge Stop Script**: Called to stop forced charging.
- **Discharge Battery Script**: Called to initiate forced discharging.
- **Discharge Stop Script**: Called to stop forced discharging.

#### 3.7. System Constants (Calibration)
- **Total Capacity**: 27.0 kWh
- **Inverter Limit**: 10.0 kW
- **Battery Limit**: 6.3 kW

#### 3.8. Options Flow (Persistence & Reconfiguration)
**CRITICAL REQUIREMENT:** The integration must provide an **Options Flow** (`async_setup_options_flow`) so that users can:
-   **Edit at Runtime**: Adjust input entities and calibration values (capacity, rates, thresholds) while the app is running, without deleting and re-adding the integration.
-   **Persistence**: Ensure that any selected input entities and configuration changes permanently persist across system reboots and integration updates.
-   Modify the 4 control script mappings.
-   The system must seamlessly merge the initial `config_entry.data` with the runtime `config_entry.options` to ensure the live configuration is always up to date.

## 4. Advanced Operational Logic (Phases 1-19)

### 4.1. FSM Target SoC Calculation (Dynamic Programming)
The system calculates required charging mathematically by constructing a 24-hour matrix of the expected Load, predicted PV, and Forecast Prices.
- **Period Compression:** Uniform blocks of identical energy direction and pricing are compressed into singular evaluation periods.
- **Tree Search:** A recursive, `@lru_cache`-accelerated solver traverses all safe capacity states between blocks to find the mathematically cheapest path to navigate physical constraints (Inverter limits, Max SoC limits).
- **Execution:** The Home Assistant event loop dispatches the DP calculation to an async thread (`async_add_executor_job`) to prevent the multi-second Python matrix calculation from blocking core execution.
- **Licensing:** The core DP algorithm module requires an embedded MIT License header.

### 4.2. UI & Web Endpoints Subsystems
- **Dashboard (`/hbc`)**: Responds with a fully standalone HTML page utilizing vanilla CSS/Lit styles. Generates an embedded SVG displaying live graphical power nodes (Grid, Solar, Battery, Home) and their dynamic usage connections.
- **Plan Table (`/hbc/plan`)**: Responds with an HTML table rendering the internal FSM JSON. Contains explicitly colored columns for `Local Time`, Import/Export rates, PV, Load, Target SoC, and Action. Limits display dynamically to Midnight-to-Midnight.

### 4.3. Solcast PV Interpolation
- Solcast provides energy-accumulated summaries by half-hour. The `SolcastSolar` manager forces linear interpolation over these spans, dividing total kWh into granular kW rates mapped purely to exact 5-minute `periodEnd` boundaries.

### 4.4. Amber Tariff Interpolation
- Amber Electric provides prices primarily in 30-minute blocks (but occasionally 5-minute blocks). The `RatesManager` splits the forecast arrays, guarantees discrete lists for `import` and `export` rates, and aligns any 30-minute rate block repetitively across the six matching 5-minute spans in the FSM array to guarantee temporal sync.

## 5. Technical Constraints
-   **Platform**: Python 3.12+ (Home Assistant environment).
-   **Timezone Safety**: All `datetime` objects must be timezone-aware (UTC), displayed in Web UI as Local time.

## 6. Development Process (Spec-Kit)
All development must follow the **Spec-Kit TDD process**. No code changes without updating the spec first.
1.  **Spec** (`@speckit.specify`) 
2.  **Plan** (`@speckit.plan`) 
3.  **Tests** (`@speckit.tester`) 
4.  **Implement** (`@speckit.implement`)
5.  **Check** (`@speckit.checker`) 
6.  **Validate** (`@speckit.validate`)
