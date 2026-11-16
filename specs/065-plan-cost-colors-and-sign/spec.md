# Feature Specification: Plan Table Cost & Tariff Color Coding and Export Cost Accounting Fixes

**Feature Branch**: `065-plan-cost-colors-and-sign`  
**Created**: 2026-11-16  
**Status**: Ready for Planning  
**Input**: User description: "Plan table cost and tariff color coding plus export cost sign and boundary duration fixes"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - At-a-Glance Semantic Color Coding for Plan Costs & Tariffs (Priority: P1)

As a battery system owner reviewing the 24-Hour Plan table across dynamic wholesale tariffs (including negative midday solar-sponge feed-in rates and evening positive feed-in spikes), I want interval costs and tariff rates to be color-coded by financial impact—green when an interval or rate earns bill credit, red/coral when an interval costs money or when exporting incurs a negative feed-in penalty, and muted neutral at zero—so I can immediately distinguish bill credits (`-$`) from bill charges (`+$`) and export penalties (`-0.06` feed-in) without misreading minus signs.

**Why this priority**: In wholesale electricity markets (Amber Electric), minus signs have opposite meanings across columns: a negative `Cost` (`-$0.20.7`) is good (a bill credit reducing total cost), whereas a negative `Export` rate (`-0.06`) is bad (a solar-sponge export penalty where exporting costs money), and a negative `Import` rate (`-0.05`) is good (getting paid to import). Without color coding, monochrome text on state-tinted rows causes confusion about whether exporting is earning or costing money.

**Independent Test**: Render the 24-Hour Plan table (both Lite production view and Debug view, in both `5min` and `30min` resolutions) with rows spanning positive expenses, negative bill credits, zero-cost self-consumption, negative feed-in penalties, positive feed-in credits, and negative import rates, and verify each cell carries the expected semantic CSS class (`val-credit`, `val-cost`, `val-neutral`) and explanatory legend/tooltips.

**Acceptance Scenarios**:

1. **Given** a plan row has a negative `Interval Cost` (e.g. `-$0.20.7` while exporting at `+0.26 $/kWh`), **When** the Plan Table renders in `5min` or `30min` resolution, **Then** the `Cost` cell renders with the credit indicator style (`val-credit`, green) showing the user is earning money.
2. **Given** a plan row has a positive `Interval Cost` (e.g. `$0.00.7` while grid-charging at `+0.02 $/kWh` or paying a penalty while exporting into a `-0.06 $/kWh` feed-in rate), **When** the Plan Table renders, **Then** the `Cost` cell renders with the expense indicator style (`val-cost`, red/coral) showing the interval adds to the electricity bill, while `$0.00.0` intervals render with `val-neutral`.
3. **Given** plan rows include negative `Export` feed-in rates (e.g. `-0.06`, exporting costs money) and positive `Export` feed-in rates (e.g. `0.26`, exporting earns credit), **When** the Plan Table renders, **Then** negative `Export` cells render as `val-cost` (red/coral warning) and positive `Export` cells render as `val-credit` (green), while negative `Import` rates (`< 0`, paid to import) also render as `val-credit` (green).
4. **Given** a user views the Plan Table, **When** inspecting column headers or the table footer legend, **Then** concise sign-convention tooltips and legend text explain `-$` green = bill credit (earning) and `+$` red = bill cost (expense / export penalty).

---

### User Story 2 - Accurate `:25` / `:55` Settlement Interval Cost Display (Priority: P1)

As a battery system owner inspecting the 5-minute 24-Hour Plan table, I need every 5-minute interval—including `:25` and `:55` half-hour boundary slots whose raw Amber forecast timestamps span `299` seconds (`:25:01` to `:30:00`)—to compute its 5-minute `Interval Cost` without truncating `4.983` minutes down to `4` minutes, and `30min` aggregation must preserve exact negative/positive interval cost sums.

**Why this priority**: Amber forecast intervals at `:25` and `:55` span `299` seconds (`4.9833` minutes). Integer truncation (`int(299 / 60) == 4`) caused every 6th row in the Plan Table to under-report `Interval Cost` by 20% (e.g. showing `-$0.16.6` instead of `-$0.20.5` at constant power and tariff).

**Independent Test**: Pass a `299`-second (`19:25:01` → `19:30:00`) rate interval at `-9.44 kW` net grid and `$0.26/kWh` export tariff into `build_diagnostic_plan_table` and verify `Interval Cost` equals `-$0.2045` (`5/60 h`) rather than `-$0.1636` (`4/60 h`), and verify `30min` matrix aggregation preserves negative cost signs regardless of `$` placement.

**Acceptance Scenarios**:

1. **Given** an Amber 5-minute forecast slot spans `299` seconds (`:25:01` to `:30:00` or `:55:01` to `:00:00`), **When** `build_diagnostic_plan_table` calculates `duration_mins`, **Then** it rounds to the nearest minute (`5` minutes) so `Interval Cost` matches adjacent 5-minute intervals of identical power and price.
2. **Given** `30min` plan matrix aggregation sums six 5-minute `Interval Cost` strings (whether formatted `$-0.2045` or `-$0.2045`), **When** `_build_plan_matrix(resolution="30min")` executes, **Then** negative credits and positive costs sum with their exact mathematical signs preserved.

---

### User Story 3 - Accurate Live Cumulative Cost Sign for Grid Exports (Priority: P1)

As a battery system owner tracking live cumulative electricity cost (`TelemetryCostTracker`), I need grid exports during positive feed-in tariffs (`+0.26 $/kWh`) to **reduce** cumulative bill cost and grid exports during negative feed-in tariffs (`-0.06 $/kWh` solar sponge) to **increase** cumulative bill cost, matching the LP solver's exact objective formula.

**Why this priority**: `TelemetryCostTracker` previously added `+(export_delta * current_price_exp)` instead of subtracting `-(export_delta * current_price_exp)`. Because Amber feed-in sensors report positive numbers for export earnings (`+0.26`) and negative numbers for export penalties (`-0.06`), the live tracker was billing the user for profitable evening exports and crediting the user for daytime export penalties.

**Independent Test**: Run `TelemetryCostTracker._on_tick` with `0.5 kWh` import at `+0.20` and `0.2 kWh` export at `+0.10` and verify cumulative cost changes by `+0.10 - 0.02 = +0.08`; run a second tick with `0.0 kWh` import and `1.0 kWh` export at `-0.06` (negative FiT penalty) and verify cumulative cost **increases** by `+$0.06`.

**Acceptance Scenarios**:

1. **Given** `0.5 kWh` is imported at `+$0.20/kWh` and `0.2 kWh` is exported at `+$0.10/kWh`, **When** `TelemetryCostTracker` processes the 5-minute tick, **Then** `cumulative_cost` changes by `(0.5 * 0.20) - (0.2 * 0.10) = +$0.08`.
2. **Given** `0.0 kWh` is imported and `1.0 kWh` is exported during a negative feed-in tariff of `-$0.06/kWh`, **When** `TelemetryCostTracker` processes the 5-minute tick, **Then** `cumulative_cost` increases by `- (1.0 * -0.06) = +$0.06` (capturing the real solar-sponge export penalty).

---

### Edge Cases

- **Near-Zero Floating-Point Dust (`-0.00001` or `+0.00002`)**: Values whose display rounds to zero (`|Cost| < 0.0005`, `|Rate| < 0.005`) MUST render as neutral (`val-neutral`) rather than flashing green or red on `$0.00.0` / `0.00`.
- **Contrast on State-Tinted Rows**: `CHARGE_GRID` rows have a `0.15` green background tint and `DISCHARGE_GRID` rows have a `0.15` red/coral background tint; `.val-credit` (`#00ff88`) and `.val-cost` (`#ff6b6b`) with `font-weight: 600` maintain high legibility across all row states.
- **Browser Asset Caching**: Panel registration URLs (`hbc-panel-lite.js?v=58` and `hbc-panel.js?v=58`) and internal child component imports must bust stale browser module caches cleanly without breaking `@web/test-runner` resolution.
- **Solver Immutability**: `custom_components/house_battery_control/fsm/lin_fsm.py` already computes `cash += imported * price_buy[i] - exported * price_sell[i]` and MUST remain completely untouched (`0` diff).

## Assumptions

- Amber Electric and Fixed TOU tariff providers represent feed-in (`export_price`) rates as positive when exporting earns a bill credit and negative when exporting incurs a bill charge/penalty.
- Existing persisted `cumulative_cost` history in Home Assistant `.storage` does not require destructive migration or reset; correcting the formula immediately makes all subsequent 5-minute billing ticks accurate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Both `<hbc-plan-table-lite>` and `<hbc-plan-table>` MUST apply semantic CSS classes to the `Cost` column in both `5min` and `30min` views:
  - `val-credit` (green `#00ff88`, bold) when numeric interval cost `< -0.0005` (net bill credit / earnings),
  - `val-cost` (red/coral `#ff6b6b`, bold) when numeric interval cost `> +0.0005` (net bill expense / export penalty),
  - `val-neutral` (muted `#8888aa`) when `|cost| <= 0.0005` (`$0.00.0`).
- **FR-002**: Both `<hbc-plan-table-lite>` and `<hbc-plan-table>` MUST apply semantic CSS classes to tariff rate columns:
  - `Export` column: `val-cost` when numeric export rate `< -0.005` (negative feed-in penalty where exporting costs money), `val-credit` when `> +0.005` (positive feed-in reward), and `val-neutral` when `|export_rate| <= 0.005`.
  - `Import` column: `val-credit` when numeric import rate `< -0.005` (negative wholesale import price where importing earns credit) and `val-neutral` when `|import_rate| <= 0.005` (leaving normal positive import rates in default text color so the column is not solid red all day).
- **FR-003**: Both `<hbc-plan-table-lite>` and `<hbc-plan-table>` MUST include explanatory `title` tooltips on the `Import`, `Export`, and `Cost` headers and a concise sign/color legend note beneath the table.
- **FR-004**: `build_diagnostic_plan_table` in `diagnostics.py` MUST compute `duration_mins = max(1, round((end - start).total_seconds() / 60.0))` so `299`-second Amber boundary intervals (`:25:01–:30:00`, `:55:01–:00:00`) evaluate as `5` minutes rather than truncating to `4` minutes.
- **FR-005**: `_build_plan_matrix` (`30min` aggregation in `coordinator.py`) MUST strip currency symbols before numeric parsing so both `$-0.2045` and `-$0.2045` preserve their negative sign when summed.
- **FR-006**: `TelemetryCostTracker._on_tick` in `telemetry_tracker.py` MUST accumulate interval cost as `(import_delta * current_price_imp) - (export_delta * current_price_exp)` so positive feed-in exports reduce cumulative cost and negative feed-in exports increase cumulative cost.
- **FR-007**: Panel `module_url` cache-busting query strings in `__init__.py` MUST be incremented (`?v=58`) and `system_requirements.md` (§2.2.1 / §2.2.2) MUST document the Plan Table semantic color coding and cost sign conventions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `100%` of negative-cost (credit) rows, positive-cost (expense/penalty) rows, and negative-export-tariff (solar-sponge penalty) rows in both `5min` and `30min` Plan Table views display distinct, unambiguous semantic styling (`val-credit` vs `val-cost` vs `val-neutral`).
- **SC-002**: `:25` and `:55` boundary intervals (`299s` duration) match standard `300s` 5-minute intervals within `0.0001` dollars (`0%` truncation error, eliminating the previous `20%` under-reporting).
- **SC-003**: Live `TelemetryCostTracker` billing delta matches the LP solver cost equation `(import_kwh * import_price) - (export_kwh * export_price)` across all four import/export price sign combinations (`+/+`, `+/-`, `-/+`, `-/-`).
- **SC-004**: `100%` of Python (`pytest`), JS (`eslint` + unit tests), and `lin_fsm.py` zero-diff checks pass.
