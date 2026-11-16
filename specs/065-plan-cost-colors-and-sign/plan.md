# Implementation Plan: Plan Table Cost & Tariff Color Coding and Export Cost Accounting Fixes

**Branch**: `065-plan-cost-colors-and-sign` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/065-plan-cost-colors-and-sign/spec.md`

## Summary

Eliminate sign ambiguity and cost-display discrepancies in the 24-Hour Plan and live billing tracker:
1. **Plan Table Semantic Color Coding (`hbc-plan-table-lite.js` & `hbc-plan-table.js`)**: Color-code `Cost` (`-$` green `.val-credit`, `+$` red `.val-cost`, `$0.00.0` muted `.val-neutral`), `Export` (`< 0` red `.val-cost` warning for negative feed-in penalties, `> 0` green `.val-credit` for feed-in earnings), and `Import` (`< 0` green `.val-credit` when paid to import), plus header tooltips and a concise sign legend beneath the table across both `5min` and `30min` views.
2. **`:25` / `:55` Boundary Duration Fix (`diagnostics.py` & `coordinator.py`)**: Round interval duration to nearest minute (`round((end - start).total_seconds() / 60.0)`) so `299s` Amber half-hour boundary slots (`:25:01–:30:00`) evaluate as `5` minutes instead of `4` minutes, and harden `$` stripping in `coordinator.py:_build_plan_matrix` `30min` summation.
3. **Live Cumulative Cost Export Sign Fix (`telemetry_tracker.py`)**: Change `+ (export_delta * current_price_exp)` to `- (export_delta * current_price_exp)` so positive feed-in exports reduce cumulative bill cost and negative feed-in exports increase cumulative bill cost, matching `lin_fsm.py:272`.
4. **Frontend Cache Bust (`__init__.py`)**: Bump panel `module_url` query string from `?v=57` to `?v=58`.

## Technical Context

**Language/Version**: Python 3.12+ (backend) & ES2022 LitElement 2.4 Web Components (frontend)  
**Primary Dependencies**: Home Assistant Core, LitElement (`unpkg.com/lit-element@2.4.0`), `@open-wc/testing` / `@web/test-runner`, `eslint`  
**Storage**: Existing Home Assistant `.storage` (`house_battery_control.cumulative_cost_v2`, schema unchanged)  
**Testing**: `pytest`, `ruff`, `npm run lint:js`, `npm test` (`web-test-runner`)  
**Target Platform**: Home Assistant 2026.11+ Custom Integration & Custom Panel  
**Project Type**: Home Assistant Custom Integration (`custom_components/house_battery_control`)  
**Constraints**: Zero changes to `fsm/lin_fsm.py`; maintain `eslint --max-warnings=0`; preserve all 16 required plan columns and `localStorage` column-toggle behavior  
**Scale/Scope**: 4 backend files (`diagnostics.py`, `coordinator.py`, `telemetry_tracker.py`, `__init__.py`), 2 frontend components (`hbc-plan-table-lite.js`, `hbc-plan-table.js`), Python + JS test suites, and `system_requirements.md`

## Gate Check

| Gate | Status | Notes |
|------|--------|-------|
| `spec.md` & `system_requirements.md` updated before code | PASS | `specs/065-plan-cost-colors-and-sign/spec.md` & `system_requirements.md` §2.2.2 updated |
| Non-destructive to `lin_fsm.py` | PASS | Zero changes to `fsm/lin_fsm.py` |
| TDD (RED before GREEN) | PASS | Enforced in `tasks.md` Phase 2 before touching production `.py` / `.js` files |
| Frontend lint & cache-bust hygiene | PASS | `?v=58` bump in `__init__.py` + `npm run lint:js` (`--max-warnings=0`) |

## Proposed Changes

### 1. Frontend Plan Tables (`custom_components/house_battery_control/frontend/hbc-plan-table-lite.js` & `hbc-plan-table.js`)
- Preserve raw numeric values (`impNum`, `expNum`, `costNum`) alongside formatted display strings when mapping `5min` and `30min` rows.
- Add helper `_cellClass(col, row)`:
  - `"Cost"`: `row.costNum < -0.0005` → `"val-credit"`, `row.costNum > 0.0005` → `"val-cost"`, else `"val-neutral"`
  - `"Export"`: `row.expNum < -0.005` → `"val-cost"`, `row.expNum > 0.005` → `"val-credit"`, else `"val-neutral"`
  - `"Import"`: `row.impNum < -0.005` → `"val-credit"`, `Math.abs(row.impNum) <= 0.005` → `"val-neutral"`, else `""`
  - Other columns: `""`
- Render `<td class="${this._cellClass(c, r)}">${colKeys[c]}</td>` and add `title` tooltips on `Import`, `Export`, and `Cost` `<th>` headers.
- Add CSS rules:
  - `td.val-credit { color: #00ff88; font-weight: 600; }`
  - `td.val-cost { color: #ff6b6b; font-weight: 600; }`
  - `td.val-neutral { color: #8888aa; }`
- Add concise sign/color legend note in the table footer caption alongside `* Synthetic Forecast Period`.

### 2. Diagnostic Plan Duration & 30-Min Matrix (`custom_components/house_battery_control/diagnostics.py` & `coordinator.py`)
- In `diagnostics.py:111`: change `duration_mins = max(1, int((end - start).total_seconds() / 60.0))` to `duration_mins = max(1, round((end - start).total_seconds() / 60.0))`.
- In `coordinator.py:323` (`_build_plan_matrix` `parse_num`): strip `"$"` before regex matching (`re.search(r"[-+]?\d*\.\d+|\d+", str(s).replace("$", ""))`) so both `$-0.2045` and `-$0.2045` retain their negative sign.

### 3. Live Telemetry Cost Tracker (`custom_components/house_battery_control/telemetry_tracker.py`)
- In `telemetry_tracker.py:154`: change
  `self.cumulative_cost += (import_delta * current_price_imp) + (export_delta * current_price_exp)`
  to
  `self.cumulative_cost += (import_delta * current_price_imp) - (export_delta * current_price_exp)`.

### 4. Panel Registration Cache Bust (`custom_components/house_battery_control/__init__.py`)
- Bump `/hbc/frontend/hbc-panel-lite.js?v=57` → `?v=58` and `/hbc/frontend/hbc-panel.js?v=57` → `?v=58`.

## Verification Plan

1. **Phase 2 (RED)**:
   - Add Python tests in `tests/test_telemetry_tracker.py` (positive FiT export credit + negative FiT export penalty), `tests/test_web.py` (`299s` `:25` boundary interval cost + `30min` negative cost matrix aggregation), and `tests/test_init.py` (`?v=58`).
   - Add JS tests in `tests/js/hbc-plan-table.test.js` and `tests/js/hbc-plan-table-lite.test.js` asserting `.val-credit`, `.val-cost`, and `.val-neutral` classes on `Cost`, `Export`, and `Import` cells in both `5min` and `30min` modes.
   - Run tests to confirm RED failure before implementation.
2. **Phase 3 (GREEN)**:
   - Apply backend and frontend changes; run `pytest`, `npm test`, and `npm run lint:js` to verify GREEN.
3. **Phase 4 (Full Suite & Guardrails)**:
   - Run `pytest tests/ -q`, `ruff check custom_components/ tests/`, `npm run lint:js`, `npm test`, and verify `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is empty.
