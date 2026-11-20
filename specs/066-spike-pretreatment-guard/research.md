# Phase 0 Research: Upstream Spike Credibility Pre-Treatment State Machine & Renewables-Gated Spike Guard

**Feature**: `066-spike-pretreatment-guard`  
**Date**: 2026-11-20

## Decision 1: Dedicated Pre-Treatment Module (`spike_credibility.py`) Outside `lin_fsm.py`

- **Decision**: Implement the 3-state spike credibility state machine (`NEAR_REALTIME`, `MIRAGE_CLAMPED`, `CREDIBLE_SCARCITY`) as a pure upstream function `pretreat_rates_timeline(rates, now, config)` in `custom_components/house_battery_control/spike_credibility.py`, called once in `HBCDataUpdateCoordinator._async_update_data` immediately after `self.rates.get_rates()`.
- **Rationale**:
  1. Preserves `lin_fsm.py` with `0` diff (non-destructive solver boundary).
  2. Keeps `coordinator.py` clean under the Strangler Pattern (Protocol 2).
  3. Ensures `RenewablesGuard`, `SolverInputs` (`lin_fsm.py`), and `build_diagnostic_plan_table` (24-Hour Plan UI) all operate on the exact same pre-treated tariff curve, while preserving `raw_import_price`, `raw_export_price`, `raw_spike`, and `spike_regime` on each interval dict for diagnostics.

## Decision 2: Empirical Thresholds from the 3.55-Million-Row SA Hindcast Sieve

- **Decision**:
  - `DEFAULT_SPIKE_NEAR_HORIZON_MINS = 30.0` (AEMO `P5MIN` vs `P30` dispatch boundary)
  - `DEFAULT_SPIKE_RENEWABLES_THRESHOLD = 25.0` (`%`)
  - `DEFAULT_MIRAGE_IMPORT_CAP = 0.60` (`$/kWh`)
  - `DEFAULT_MIRAGE_EXPORT_CAP = 0.35` (`$/kWh`)
  - `DEFAULT_SCARCITY_HORIZON_SHORT_MINS = 360.0` (`6h`), `SHORT_WEIGHT = 0.70`, `LONG_WEIGHT = 0.40`
  - `DEFAULT_SCARCITY_IMPORT_CAP = 1.50` (`$/kWh`), `DEFAULT_SCARCITY_EXPORT_CAP = 1.20` (`$/kWh`)
- **Rationale**:
  - Across `3,076,316` Home Assistant pairs (`April + Nov 2026`), `99.8%` of `> 30 min` November export forecasts `> $0.60/kWh` failed to materialize, and clamping `> 30m` high-renewables intervals cut Export Raw MAE by `76.4%` (`$0.2054 → $0.0485/kWh`) and increased live 10-day battery earnings by `+53%` to `+117%`.
  - Across `473,815` AEMO `SA1` `P30` runs (`Jan, Feb, Apr, Jun, Jul, Oct 2026`), spike realization probability jumped from `2.4%–7.2%` at `renewables > 25%` to `67.5%–78.9%` at `renewables <= 25%` within `6h` (`40.9%` beyond `6h`), earning `+$398.95` across 4 real mega-spike days (`+$95.76` ahead of a blind `60c` cap).

## Decision 3: Drop `.high` Inflation in `RatesManager` & Gate `RenewablesGuard.spike_triggered`

- **Decision**:
  1. In `RatesManager._parse_amber_express_entity`, use unbiased `advanced_price_predicted.predicted` (falling back to `per_kwh` / `value`), removing Feature `029`'s upward substitution of `.high`. Also support `interval.get("time")` for non-detailed Amber Express entities and extract `renewables` in `_parse_entity` when present in standard Amber forecasts.
  2. In `RenewablesGuard.evaluate`, only set `spike_triggered = True` if a `spike` interval in `rates[:144]` has `renewables is None` or `renewables <= spike_renewables_threshold` (default `25.0%`), and target `100.0%` SoC by `16:00` so credible SA scarcity warnings fill the `27 kWh` battery completely.
  3. In `SyntheticRatesPredictor._average_curves`, use `statistics.median` for `pricing_curve` and `export_curve` (retaining `mean` for `load_curve`).
- **Rationale**: Eliminates all four phantom-spike pathways identified in the audit without affecting Fixed TOU or legacy non-renewables callers (`renewables is None` safely passes through).
