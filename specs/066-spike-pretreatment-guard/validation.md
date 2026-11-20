# Validation Report: Feature `066-spike-pretreatment-guard` (`v1.9.0-beta.20`)

**Date**: 2026-11-20  
**Branch**: `066-spike-pretreatment-guard`

## 1. Requirements & Acceptance Validation

| Requirement | Status | Verification Evidence |
|---|---|---|
| **FR-001 / FR-002**: 3-state upstream pre-treatment (`NEAR_REALTIME` `<= 30m`, `MIRAGE_CLAMPED` `> 30m & ren > 25%`, `CREDIBLE_SCARCITY` `> 30m & ren <= 25%`) | PASS | `custom_components/house_battery_control/spike_credibility.py`; verified in `tests/test_spike_credibility.py` (5 unit tests) and `tests/test_coordinator.py` |
| **FR-003**: Unbiased `advanced_price_predicted.predicted` in Amber Express (`rates.py`) + `{"time", "value"}` schema + optional standard `renewables` | PASS | `custom_components/house_battery_control/rates.py`; verified in `tests/test_rates.py::test_amber_express_uses_unbiased_predicted_without_high_inflation` & `test_amber_express_time_and_value_schema_and_standard_renewables` |
| **FR-004**: `RenewablesGuard` credible spike gating (`renewables <= spike_renewables_threshold`) + `100%` SoC daytime pre-charge target | PASS | `custom_components/house_battery_control/renewables_guard.py`; verified in `tests/test_renewables_guard.py` & `tests/test_coordinator.py` |
| **FR-005**: `SyntheticRatesPredictor` uses `statistics.median` for `pricing_curve` & `export_curve` | PASS | `custom_components/house_battery_control/rates_predictor.py`; verified in `tests/test_rates_predictor.py::test_synthetic_curves_use_median_to_reject_single_day_spike_outlier` |
| **FR-006**: Runtime configuration (`spike_renewables_threshold`, `mirage_import_cap`, `mirage_export_cap`) in `Control Services` | PASS | `custom_components/house_battery_control/config_flow.py`, `strings.json`, `translations/en.json`; verified in `tests/test_config_flow.py::test_spike_pretreatment_constants_and_translations` |
| **Architectural Boundary**: Zero changes to `custom_components/house_battery_control/fsm/lin_fsm.py` | PASS | `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is completely empty (`0` lines) |

## 2. Automated Test & Static Analysis Summary

- **Python Test Suite (`pytest tests/ -q`)**: `376 passed, 2 xfailed` (`43.51s`)
- **Frontend Test Suite (`npm test`)**: `6/6 test files | 21 passed, 0 failed` (`1.2s`)
- **Python Linter (`ruff check custom_components/ tests/`)**: `All checks passed!` (`0` errors)
- **JS Linter (`npm run lint:js`)**: `0` warnings / `0` errors (`--max-warnings=0`)
- **Version Bump**: `manifest.json` and `hacs.json` bumped to `1.9.0-beta.20`
