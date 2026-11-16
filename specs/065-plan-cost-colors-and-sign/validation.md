# Feature 065 Validation Report

**Feature**: `065-plan-cost-colors-and-sign`  
**Target Version**: `v1.9.0-beta.19`  
**Date**: 2026-11-16

## Spec-vs-Implementation Verification

| Requirement | Status | Evidence |
| :--- | :--- | :--- |
| **FR-001**: `Cost` semantic color classes (`val-credit`, `val-cost`, `val-neutral`) across `5min` & `30min` | PASS | Implemented in `hbc-plan-table-lite.js` & `hbc-plan-table.js`; verified in `tests/js/hbc-plan-table-lite.test.js` & `tests/js/hbc-plan-table.test.js` |
| **FR-002**: `Export` (`< 0` red penalty, `> 0` green credit) & `Import` (`< 0` green credit) semantic color classes | PASS | Implemented in `hbc-plan-table-lite.js` & `hbc-plan-table.js`; verified in Chrome via `@web/test-runner` |
| **FR-003**: Column header `title` tooltips & footer sign legend | PASS | Verified on `Import`, `Export`, and `Cost` `<th>` elements and `.table-legend` |
| **FR-004**: `:25` / `:55` `299s` boundary duration rounding (`round(...)` -> `5` min) | PASS | Implemented in `diagnostics.py:111`; verified by `test_plan_table_299s_boundary_duration_not_truncated` (`$-0.2045`) |
| **FR-005**: `$`-safe `30min` matrix summation in `coordinator.py` | PASS | Implemented in `coordinator.py:323`; verified by `test_plan_matrix_30min_preserves_negative_interval_cost_sign` (`-$1.2000`) |
| **FR-006**: Live `TelemetryCostTracker` export delta sign `- (export_delta * current_price_exp)` | PASS | Implemented in `telemetry_tracker.py:154`; verified by `test_tick_standard_accumulation` (`100.08`) & `test_tick_negative_export_tariff_increases_cost` (`100.06`) |
| **FR-007**: Panel cache-bust `?v=58` & `system_requirements.md` §2.2.2 updated | PASS | Verified by `test_panel_cache_bust_v58_and_dashboard_solver_card` |
| **Immutable Solver Core (`lin_fsm.py`)** | PASS | `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is empty (`0` lines changed) |

## Test & Static Analysis Summary

- **Python Unit & Replay Suite**: `pytest tests/ -q` → **`365 passed, 2 xfailed`** in `40.09s`
- **Browser Web Component Tests**: `npm test` (`web-test-runner` / Headless Chrome) → **`21 passed, 0 failed`** (`6/6` test files) in `0.7s`
- **Python Linter**: `ruff check custom_components/ tests/` → **All checks passed!**
- **JavaScript Linter**: `npm run lint:js` (`eslint --max-warnings=0`) → **`0` errors, `0` warnings**
