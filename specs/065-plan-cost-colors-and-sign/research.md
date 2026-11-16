# Phase 0 Research: Plan Table Cost & Tariff Color Coding and Export Cost Accounting Fixes

**Feature**: `065-plan-cost-colors-and-sign`  
**Date**: 2026-11-16

## Decision 1: Semantic Color Palette & Thresholds for Plan Table Columns

- **Decision**:
  - Introduce three semantic CSS classes in both `hbc-plan-table-lite.js` and `hbc-plan-table.js`:
    - `.val-credit`: `color: #00ff88; font-weight: 600;` (matches `hbc-dashboard.js` `.solver-green` and `.battery-item .flow-value`)
    - `.val-cost`: `color: #ff6b6b; font-weight: 600;` (matches `.err-card` `#ff6b6b` coral red, readable on `#1a1a3e`, `#15153a`, and all `0.15`-alpha row tints)
    - `.val-neutral`: `color: #8888aa;` (muted neutral matching existing `.tabs button` / `.stat-label`)
  - Column rules (evaluated on raw numeric value before `$0.00.0` string formatting):
    - **`Cost` (`Interval Cost`)**:
      - `costNum < -0.0005` → `val-credit` (green: net bill credit / earning money, e.g. `-$0.20.7`)
      - `costNum > +0.0005` → `val-cost` (red: net bill charge / spending money or export penalty, e.g. `$0.00.7`)
      - `|costNum| <= 0.0005` → `val-neutral` (muted `$0.00.0`)
    - **`Export` (`Export Rate`)**:
      - `expNum < -0.005` → `val-cost` (red: negative feed-in solar-sponge penalty — exporting costs money)
      - `expNum > +0.005` → `val-credit` (green: positive feed-in credit — exporting earns money)
      - `|expNum| <= 0.005` → `val-neutral`
    - **`Import` (`Import Rate`)**:
      - `impNum < -0.005` → `val-credit` (green: negative wholesale import tariff — paid to import)
      - `|impNum| <= 0.005` → `val-neutral`
      - `impNum > +0.005` → default text color (`#e0e0e0`), avoiding painting all positive daytime/overnight import rates red.
- **Rationale**: Resolves the visual sign inversion between bill-impact `Cost` (`-$` = good) and `Export` rate (`-0.06` = bad) without overwhelming normal positive `Import` cells. Deadband thresholds (`0.0005` for `$0.00.0` sub-cent costs, `0.005` for `0.00` two-decimal rates) prevent floating-point noise from tinting zero cells.
- **Alternatives considered**:
  - Coloring positive `Import` rates red: rejected because `Import` is positive ~98% of intervals, creating visual fatigue.
  - Background cell fills instead of text color: rejected because rows already use background tints for `FSM State` (`SELF_CONSUMPTION`, `CHARGE_GRID`, `DISCHARGE_GRID`).

## Decision 2: `:25` and `:55` Boundary Duration Calculation in `diagnostics.py`

- **Decision**: Replace `duration_mins = max(1, int((end - start).total_seconds() / 60.0))` at `diagnostics.py:111` with `duration_mins = max(1, round((end - start).total_seconds() / 60.0))`, and strip `$` before regex parsing in `coordinator.py:_build_plan_matrix` (`parse_num`).
- **Rationale**: Amber Electric half-hour boundary slots run e.g. `19:25:01` to `19:30:00` (`299s` = `4.9833` minutes). `int(...)` truncated `4.9833` to `4` minutes (`-20%` interval cost error on every `:25` and `:55` row). `round(...)` yields `5` minutes for `299s` and `300s`, `30` minutes for `1799s` and `1800s`, and `max(1, ...)` guards `0s` degenerate intervals. Stripping `$` in `coordinator.py:parse_num` guarantees both `$-0.2045` and `-$0.2045` parse as `-0.2045`.
- **Alternatives considered**: Exact floating-point `(end - start).total_seconds() / 3600.0` without rounding: rejected because Amber's `1`-second start offset (`:25:01`) represents a full `5.0`-minute settlement block in the LP solver (`dt = 5/60 h`), not `299/3600 h`.

## Decision 3: Live `TelemetryCostTracker` Export Sign Alignment

- **Decision**: Update `telemetry_tracker.py:154` from `+ (export_delta * current_price_exp)` to `- (export_delta * current_price_exp)`.
- **Rationale**: Verified against live Amber Express sensor snapshots (`API Data/*.json`) and `lin_fsm.py:272` (`cash += imported * price_buy[i] - exported * price_sell[i]`): `export_delta >= 0` (`kWh` exported) and `current_price_exp` is positive (`+0.26`) when earning feed-in credit and negative (`-0.06`) during solar-sponge export penalties. Subtracting `export_delta * current_price_exp` reduces cumulative cost when earning credit and increases cumulative cost when exporting into a negative feed-in tariff.
- **Alternatives considered**: Inverting `current_price_exp` upstream: rejected because `CONF_TRACKER_EXPORT_PRICE` reads the raw Home Assistant entity state directly.

## Decision 4: Panel Cache Busting

- **Decision**: Increment `module_url` in `custom_components/house_battery_control/__init__.py` from `?v=57` to `?v=58` on both `/hbc/frontend/hbc-panel-lite.js?v=58` and `/hbc/frontend/hbc-panel.js?v=58` (keeping relative child imports bare in `hbc-panel-lite.js` / `hbc-panel.js` so `@web/test-runner` resolves them cleanly while `StaticPathConfig(..., False)` serves `Cache-Control: no-cache`). Update `tests/test_init.py` accordingly.
- **Rationale**: Matches the established pattern from Feature `063` (`926b750`) and preserves `@web/test-runner` module resolution.
