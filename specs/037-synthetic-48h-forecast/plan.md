# 037: Synthetic 48h LP Solver Horizon

Provide an extended optimization horizon by supplementing Amber's live D+0/D+1 rates with a synthesized tail of data. The system uses targeted iterative queries against Home Assistant's native SQLite database to identify analog days based on like-for-like Solcast forecasting, and pulls their price histories to synthesize an expected pattern.

## Proposed Changes

### Phase 1: The Analog Search Engine (Observation Mode)

#### [NEW] `rates_predictor.py`
Create a new dedicated class `SyntheticRatesPredictor` designed for extreme database efficiency.
- Predictor checks `sensor.solcast_pv_forecast_tomorrow`.
- If the new forecast drifts outside $\pm 2$ kWh of `last_calculated_solar_kwh`, trigger a background HA database search.
- Retrieve the 5 mathematically closest historical days and average their prices.

#### [MODIFY] `sensor.py`
Create a new diagnostic sensor: `sensor.hbc_synthetic_rates_diagnostic`.
This sensor will be entirely passive, exposing the inner workings natively in Home Assistant.

#### [MODIFY] `web.py`
Expose the `SyntheticRatesPredictor` data via a new backend API endpoint (e.g. `/hbc/api/synthetic_outlook`).

#### [MODIFY] `frontend/hbc-panel.js` (The UI Presentation)
Add a "Tomorrow's Outlook" (or "Diagnostics") tab to the House Battery Control panel.
- **The Trigger**: The tab will feature a "Calculate Tomorrow's Outlook" button (or display auto-fetched data).
- **The Statistics Pane**: Discloses exactly which 5 dates were chosen from the database, what their solar totals were, and the target solar forecast we matched them against.
- **The Presentation Table**: Renders a standard table showing `Time`, `Synthesized Import Price`, and `Synthesized Export Price`, giving you a visual gut-check on the synthesized data.

---

### Phase 2: LP Solver Wiring (Actioned Later)

Once you have verified the data output in the new frontend tab over several days and are mathematically satisfied with the matching logic and price outputs, we will begin Phase 2.

#### [MODIFY] `rates.py` & `load.py`
- Update the interfaces to allow padding pricing and load curves up to a max of 576 steps.

#### [MODIFY] `coordinator.py` & LP Math
- Truncate all input arrays to exactly match the length of the available Solcast data.
- Feed the dynamic 48h array into the Scipy LP Matrix.
