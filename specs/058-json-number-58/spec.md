# Feature Specification: 058 - Fix Amber Express Mapping & Solar Guard Refinement

## 1. Description
This feature addresses a critical disconnect in the configuration options where selecting "Use Amber Express" did not properly route the newly configured Amber Express detailed sensors to the main pricing evaluator. It also ensures the "Solar Guard" correctly handles the scenario where today's solar forecast is extremely low, guaranteeing the battery charges ahead of the evening peak.

## 2. User Scenarios & Testing

### Scenario 1: Amber Express Configuration
- **Given** the user checks "Use Amber Express nested array format" in the integration options.
- **And** assigns the Amber Express "Detailed" sensors to the Import/Export entity fields.
- **When** the integration fetches the latest rates from Amber.
- **Then** the `RatesManager` uses the detailed entities to extract the `advanced_price_predicted` interpolation rather than falling back to the standard generic forecast.

### Scenario 2: Low Solar Today Guard
- **Given** the user has configured the Solar Guard thresholds and deadlines.
- **And** the `Solcast Forecast Today` falls below the configured low solar threshold.
- **When** the system generates the 24h operational plan.
- **Then** the Low Renewables Guard is activated.
- **And** the solver forces the battery to charge from the grid prior to the configured daytime deadline (e.g. 15:00) to ensure capacity for the evening peak.

## 3. Functional Requirements
1. **Config Mapping Correction:**
   - Modify `coordinator.py` to route `CONF_CURRENT_IMPORT_PRICE_ENTITY` and `CONF_CURRENT_EXPORT_PRICE_ENTITY` into the `RatesManager` instantiation when `CONF_USE_AMBER_EXPRESS` is True.
   - If the current entities are unconfigured, fall back safely to the forecast entities.
2. **Solar Guard Logic Verification:**
   - Ensure the existing `solcast_today` condition in `RenewablesGuard.evaluate` effectively triggers the daytime deadline constraint when solar is low.
   - Ensure `solcast_today` defaults correctly when the entity is not configured or unavailable to prevent false triggers.

## 4. Success Criteria
- The dashboard plan clearly reflects interpolated pricing (e.g., 160c/kWh feed-in prices) rather than identical fallback pricing.
- The solver output proves the battery charges proactively during the day when Solcast reports low expected yield for the current day.

## 5. Assumptions and Dependencies
- The Amber Express detailed sensors natively expose a `forecasts` list attribute that contains the `advanced_price_predicted` dictionaries.
- The Solar Guard thresholds are already exposed in the UI configuration.
