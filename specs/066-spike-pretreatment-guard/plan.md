# Implementation Plan: Upstream Spike Credibility Pre-Treatment State Machine & Renewables-Gated Spike Guard

**Branch**: `066-spike-pretreatment-guard` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/066-spike-pretreatment-guard/spec.md`

## Summary

Implement the empirically validated 2-rule / 3-state **Upstream Spike Credibility Pre-Treatment State Machine** and **Renewables-Gated Spike Guard** strictly outside `lin_fsm.py`:
1. **`spike_credibility.py` (New Pure Pre-Treatment Module)**: Classifies every 5-minute forecast interval into `NEAR_REALTIME` (`<= 30m` or `renewables is None` → uncapped), `MIRAGE_CLAMPED` (`> 30m` & `renewables > 25%` → clamp `import <= $0.60`, `export <= $0.35`, clear `spike = False`), or `CREDIBLE_SCARCITY` (`> 30m` & `renewables <= 25%` → `0.70×` weight `<= 6h`, `0.40×` `> 6h`, capped at `$1.50` / `$1.20`, keep `spike`).
2. **`RatesManager` (`rates.py`)**: Use unbiased `advanced_price_predicted.predicted` (removing `.high` tail-risk inflation), support `time` key on newer Amber Express forecasts, and preserve `renewables` on standard Amber forecast dicts when present.
3. **`RenewablesGuard` (`renewables_guard.py`)**: Require `r.get("renewables") is None or float(r["renewables"]) <= spike_renewables_threshold` (`25.0%` default) for `spike_triggered`, and fill to **`100.0%` SoC** by the daytime deadline (`16:00` default) when triggered.
4. **`SyntheticRatesPredictor` (`rates_predictor.py`)**: Aggregate `pricing_curve` and `export_curve` across the 5 analog days via `statistics.median` instead of arithmetic mean.
5. **`HBCDataUpdateCoordinator` & Config Flow (`coordinator.py`, `const.py`, `config_flow.py`, `strings.json`, `translations/en.json`)**: Wire `pretreat_rates_timeline` before `RenewablesGuard` and `SolverInputs`, and expose `spike_renewables_threshold`, `mirage_import_cap`, and `mirage_export_cap` in **Options → Control Services**.

## Technical Context

**Language/Version**: Python 3.12+ (Home Assistant Custom Integration)  
**Primary Dependencies**: Home Assistant Core (`dt_util`, `voluptuous`, `selector`), Python stdlib (`statistics`, `datetime`)  
**Storage**: Home Assistant `ConfigEntry` options (`spike_renewables_threshold`, `mirage_import_cap`, `mirage_export_cap`)  
**Testing**: `pytest`, `pytest-asyncio`, `ruff`, `npm test`, `npm run lint:js`  
**Constraints**: **Zero changes to `fsm/lin_fsm.py`** (`0` diff); Strangler Pattern via dedicated `spike_credibility.py`; full backward compatibility when `renewables is None` (Fixed TOU / basic sensors)

## Gate Check

| Gate | Status | Notes |
|------|--------|-------|
| `spec.md` & `system_requirements.md` updated before code | PASS | `specs/066-spike-pretreatment-guard/spec.md` & `system_requirements.md` §4.4–4.5 updated |
| Non-destructive to `lin_fsm.py` | PASS | Pure upstream pre-treatment (`0` diff on `lin_fsm.py`) |
| Strangler Pattern (Protocol 2) | PASS | Core state machine isolated in `custom_components/house_battery_control/spike_credibility.py` |
| TDD (RED before GREEN) | PASS | Enforced in `tasks.md` prior to any production `.py` edits |

## Proposed Changes

### 1. Constants (`custom_components/house_battery_control/const.py`)
- Config keys:
  - `CONF_SPIKE_RENEWABLES_THRESHOLD = "spike_renewables_threshold"`
  - `CONF_MIRAGE_IMPORT_CAP = "mirage_import_cap"`
  - `CONF_MIRAGE_EXPORT_CAP = "mirage_export_cap"`
- Defaults:
  - `DEFAULT_SPIKE_RENEWABLES_THRESHOLD = 25.0`
  - `DEFAULT_MIRAGE_IMPORT_CAP = 0.60`
  - `DEFAULT_MIRAGE_EXPORT_CAP = 0.35`
  - `DEFAULT_SPIKE_NEAR_HORIZON_MINS = 30.0`
  - `DEFAULT_SCARCITY_HORIZON_SHORT_MINS = 360.0`
  - `DEFAULT_SCARCITY_SHORT_WEIGHT = 0.70`
  - `DEFAULT_SCARCITY_LONG_WEIGHT = 0.40`
  - `DEFAULT_SCARCITY_IMPORT_CAP = 1.50`
  - `DEFAULT_SCARCITY_EXPORT_CAP = 1.20`
- Regime constants:
  - `SPIKE_REGIME_NEAR_REALTIME = "NEAR_REALTIME"`
  - `SPIKE_REGIME_MIRAGE_CLAMPED = "MIRAGE_CLAMPED"`
  - `SPIKE_REGIME_CREDIBLE_SCARCITY = "CREDIBLE_SCARCITY"`

### 2. Upstream Pre-Treatment State Machine (`custom_components/house_battery_control/spike_credibility.py` — NEW)
- `pretreat_rates_timeline(rates: list[dict[str, Any]], now: datetime, config: dict[str, Any] | None = None) -> list[dict[str, Any]]`:
  - Returns shallow-copied dicts with `raw_import_price`, `raw_export_price`, `raw_spike`, and `spike_regime`.
  - Computes `lead_mins = (start - now).total_seconds() / 60.0`.
  - Applies `NEAR_REALTIME`, `MIRAGE_CLAMPED`, or `CREDIBLE_SCARCITY` deterministically.

### 3. Unbiased Amber Parsing & Standard Renewables Preservation (`custom_components/house_battery_control/rates.py`)
- In `_parse_amber_express_entity`:
  - Accept `interval.get("start_time") or interval.get("periodStart") or interval.get("time", "")`.
  - Set `price = float(advanced.get("predicted", fallback_price))` directly (removing the `.high` upward blend).
- In `_parse_entity`:
  - Extract `float(interval["renewables"])` when `interval.get("renewables") is not None`, else `None`.

### 4. Renewables-Gated Spike Guard (`custom_components/house_battery_control/renewables_guard.py`)
- Add optional `spike_renewables_threshold: float = 25.0` parameter to `RenewablesGuard.evaluate(...)`.
- Set `self.spike_triggered = any(bool(r.get("spike")) and (r.get("renewables") is None or float(r["renewables"]) <= spike_renewables_threshold) for r in rates[:144])`.
- Set `self.target_soc = 100.0` for all active guard states (both low-energy and credible SA scarcity spike warnings fill to `100%`!).

### 5. Median Synthetic Analog Curves (`custom_components/house_battery_control/rates_predictor.py`)
- In `_average_curves(analog_days, attr_name)`:
  - Use `statistics.median` at each of the 288 steps when `attr_name in ("pricing_curve", "export_curve")` (keeping arithmetic mean for `load_curve`).

### 6. Coordinator Wiring & Options Flow (`coordinator.py`, `config_flow.py`, `strings.json`, `translations/en.json`)
- In `coordinator.py:_async_update_data`:
  - Run `rates_timeline = pretreat_rates_timeline(self.rates.get_rates(), dt_util.utcnow(), self.config)` once after `self.rates.update()` and use `rates_timeline` everywhere downstream (`RenewablesGuard.evaluate(..., spike_renewables_threshold=...)`, `extended_rates_timeline`, `rates` diagnostic output).
- In `config_flow.py` (`async_step_control` in both initial ConfigFlow and OptionsFlow) + `strings.json` + `translations/en.json`:
  - Add optional `NumberSelector` inputs for `CONF_SPIKE_RENEWABLES_THRESHOLD`, `CONF_MIRAGE_IMPORT_CAP`, and `CONF_MIRAGE_EXPORT_CAP`.

## Verification Plan

1. **Phase 2 (RED)**:
   - Create `tests/test_spike_credibility.py` testing all 3 regimes, negative tariff preservation, `renewables is None` pass-through, and custom config caps.
   - Update/add tests in `tests/test_renewables_guard.py` (high-renewables spike suppressed vs low-renewables `<= 25%` spike activating `100%` target), `tests/test_rates.py` (no `.high` inflation, `time` key support, standard Amber `renewables` extraction), `tests/test_rates_predictor.py` (`median` outlier immunity), `tests/test_coordinator.py` (end-to-end pre-treatment + credible spike guard), and `tests/test_config_flow.py`.
   - Run `pytest` to confirm RED failure.
2. **Phase 3 (GREEN)**:
   - Implement `const.py`, `spike_credibility.py`, `rates.py`, `renewables_guard.py`, `rates_predictor.py`, `coordinator.py`, `config_flow.py`, `strings.json`, and `translations/en.json`.
   - Verify all tests pass GREEN.
3. **Phase 4 (Full Suite)**:
   - Run `pytest tests/ -q`, `ruff check custom_components/ tests/`, `npm test`, `npm run lint:js`, and verify `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is empty (`0` diff).
