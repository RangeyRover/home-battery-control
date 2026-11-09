# v1.9.0-beta.17 — Solver telemetry & Amber spike 80% pre-charge

This prerelease adds non-destructive LP/MIP solver budget & telemetry visibility (**US4**) and automatic pre-charging to **80% SoC by 16:00** when Amber forecasts a price spike within the next 12 hours (**US5**).

## Highlights

- **Non-Destructive Solver Time Budget & Dashboard Visibility (`US4`):**
  - Increases default LP/MIP solve budget from `15.0s` to `30.0s` (configurable in **Options → Energy & Metrics** from `1s` to `60s`).
  - Records `SolverStats` (`solve_seconds`, `budget_seconds`, `passes`, `integer_used`, `reference_solve`, `outcome`, `detail`, `horizon_steps`) and 24-hour rolling peak solve duration (`solve_seconds_max_24h`).
  - Adds diagnostic entity `sensor.house_battery_control_solver_duration` (`hbc_solve_time`) and a **Solver** card + timeout/no-plan constraint badge on the HBC dashboard (`?v=57`).
  - Restores missing translation labels for `reserve_soc`, `round_trip_efficiency`, and `export_margin` in **Energy & Metrics**.
- **Amber Spike Pre-Charge: 80% SoC by 16:00 (`US5`):**
  - Preserves `spike_status` (`"potential_spike"` / `"spike"`) and `descriptor == "spike"` from Amber and Amber Express forecast intervals (`RateInterval.spike`).
  - Automatically triggers `"Amber Spike Forecast"` in `RenewablesGuard` when any interval in the next 12 hours (`144` steps) forecasts a spike, regardless of `AND`/`OR` Solcast mode.
  - Targets **80% SoC by 16:00** (`DEFAULT_GUARD_DAYTIME_DEADLINE = "16:00"`, omitting the `05:00` overnight deadline when spike-only) so the battery tops up using cheap daytime power, avoids forced charging during the expensive 16:00–19:00 ramp, and stays free to discharge during the evening spike.

## Validation

- Full test suite: `353 passed, 2 xfailed` (`pytest tests/ -q`).
- Linters: `ruff check custom_components/ tests/` and `npm run lint:js` passed with 0 errors and 0 warnings.
