# Feature Specification: Upstream Spike Credibility Pre-Treatment State Machine & Renewables-Gated Spike Guard

**Feature Branch**: `066-spike-pretreatment-guard`  
**Created**: 2026-11-20  
**Status**: Ready for Planning  
**Input**: User description: "Adjust the Low Renewables Guard to require low SA renewables for spike warnings, and implement the two-rule upstream pre-treatment spike credibility state machine outside lin_fsm.py"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upstream Pre-Treatment Mirage Clamp on High-Renewables Distant Spikes (Priority: P1)

As a South Australian battery system owner on wholesale tariffs (Amber / Amber Express), when forecast intervals more than 30 minutes ahead (`lead_time > 30 min`, AEMO `P30` pre-dispatch) claim extreme import or export spikes while that interval's grid renewables exceed `25%` (`93%–99.8%` empirical false-spike rate), I want HBC's upstream pre-treatment layer to clamp speculative export prices at `$0.35/kWh` and import prices at `$0.60/kWh` (and drop Amber Express's `.high` tail-risk inflation) before passing prices to `lin_fsm.py`—so the solver still fills up opportunistically on cheap solar/midday power without paying expensive grid rates, spilling solar into negative feed-in penalties, or hoarding past real `25c–35c` early-evening prices waiting for a `$12` mirage.

**Why this priority**: Across 3.07 million Home Assistant forecast-vs-settled pairs and 6 months of AEMO `SA1` history, `99.8%` of `> 30 min` November export forecasts `> $0.60/kWh` (mean `$4.10/kWh`) were phantom pre-dispatch artifacts that settled at `$0.28/kWh`, and Feature `029`'s `.high` blend inflated forecast MAE by over `2×`. Clamping mirages upstream leaves `lin_fsm.py` completely untouched while doubling calm-week battery earnings.

**Independent Test**: Pass a 24-hour rate timeline containing a `$12.17/kWh` import / `$4.10/kWh` export spike `4 hours` ahead with `renewables = 68%` into `pretreat_rates_timeline` and verify the interval enters `MIRAGE_CLAMPED` with `import_price == 0.60`, `export_price == 0.35`, and `spike == False`, while preserving `raw_import_price`, `raw_export_price`, and `raw_spike`.

**Acceptance Scenarios**:

1. **Given** a forecast interval has `lead_time > 30 min` and `renewables > 25.0%` (e.g. `68%`), **When** upstream pre-treatment evaluates the timeline, **Then** `export_price` is clamped to `min(export_price, 0.35)`, `import_price` is clamped to `min(import_price, 0.60)`, and `spike` is set `False` (`spike_regime = "MIRAGE_CLAMPED"`).
2. **Given** an Amber Express sensor provides `advanced_price_predicted.{low, predicted, high}`, **When** `RatesManager` parses import and export intervals, **Then** it extracts unbiased `predicted` (never substituting the 90th-percentile `.high` fan) and preserves `renewables` on both Amber Express and standard Amber forecast intervals when present.
3. **Given** normal non-spike intervals (`import_price <= 0.60`, `export_price <= 0.35`, including negative solar-sponge tariffs like `-0.06`), **When** pre-treatment runs, **Then** prices pass through unchanged so normal arbitrage and negative-tariff logic operate identically.

---

### User Story 2 - Uncapped Near-Real-Time (`<= 30m`) & Probability-Weighted Low-Renewables Scarcity (`<= 25%`) (Priority: P1)

As the battery system owner, when a forecast spike is **either** imminent within AEMO's 5-minute dispatch window (`lead_time <= 30 min`) **or** backed by genuine SA wind/solar drought hours in advance (`interval.renewables <= 25%`, where `64%–79%` of spikes materialize), I want pre-treatment to pass uncapped prices inside `<= 30 min` and probability-weighted scarcity prices (`0.70×` excess within `<= 6h`, `0.40×` beyond `> 6h`, saturation-capped at `$1.20/kWh` export and `$1.50/kWh` import) beyond `30 min` so the `27 kWh` battery starts filling 4–6 hours early before real multi-hour scarcity events and discharges at full `10 kW` when real spikes hit.

**Why this priority**: A blind `60c` or `35c` cap beyond `30 min` lost `$70–$165` across real 2026 SA mega-spike days (`Jan 26`, `Jul 08`) because `30 minutes` is too late to charge a `27 kWh` battery at `6.3 kW`. Lifting the mirage clamp whenever `interval.renewables <= 25%` captured `+$25.81` more profit than current HBC (`+$95.76` ahead of a blind `60c` cap) on real mega-spike days.

**Independent Test**: Pass a timeline with (a) a `$3.50/kWh` spike at `lead_time = 20 min` (`renewables = 90%`) and (b) a `$2.00/kWh` export spike at `lead_time = 180 min` (`renewables = 12%`) into `pretreat_rates_timeline` and verify (a) passes through `100%` uncapped (`NEAR_REALTIME`) while (b) applies `0.35 + 0.70 * (2.00 - 0.35) -> $1.20` (`CREDIBLE_SCARCITY`) with `spike` preserved.

**Acceptance Scenarios**:

1. **Given** any interval has `lead_time <= 30 min` (regardless of `renewables`), **When** pre-treatment evaluates it, **Then** `import_price`, `export_price`, and `spike` remain `100%` uncapped (`spike_regime = "NEAR_REALTIME"`).
2. **Given** a forecast interval has `lead_time > 30 min` and `renewables <= 25.0%` (genuine SA scarcity), **When** pre-treatment evaluates it, **Then** spike excess above `$0.60` import / `$0.35` export is weighted by `0.70` (`<= 6h` ahead) or `0.40` (`> 6h` ahead), capped at `$1.50` import / `$1.20` export (`spike_regime = "CREDIBLE_SCARCITY"`).
3. **Given** Fixed TOU mode or a tariff interval with `renewables is None`, **When** pre-treatment evaluates it, **Then** prices pass through unchanged for full backward compatibility.

---

### User Story 3 - Renewables-Gated Spike Pre-Charge in `RenewablesGuard` & Median Synthetic Tail (Priority: P1)

As the battery system owner, when Amber flags a spike warning within the next 12 hours, I want `RenewablesGuard` to force pre-charging (`100%` SoC by `16:00` daytime deadline) **only** when that spike interval is credible (`interval.renewables <= 25%`, or `<= 30 min` imminent, or `renewables is None`), while ignoring phantom high-renewables spike warnings—and I want the 24h–48h synthetic analog predictor to aggregate historical analog price curves via `median` rather than `mean` so a single historical `$21/kWh` spike day cannot inject phantom `$4/kWh` spikes into tomorrow's tail.

**Why this priority**: Previously, `RenewablesGuard` set `spike_triggered = True` on any `spike` flag in `rates[:144]` even at `88%` renewables, bypassing `AND`/`OR` mode and forcing grid charging on windy sunny days. Gating `spike_triggered` on interval `renewables <= spike_renewables_threshold` (default `25%`) and targeting `100%` SoC ensures forced grid top-up only fires when SA scarcity is real.

**Independent Test**: Evaluate `RenewablesGuard` with a `spike: True` interval at `renewables: 68%` (verify `spike_triggered is False` and guard stays inactive) vs `spike: True` at `renewables: 18%` (verify `spike_triggered is True`, `target_soc == 100.0`, and `16:00` deadline resolves); test `SyntheticRatesPredictor._average_curves` with 4 normal `$0.20` days + 1 `$20.00` spike day and verify synthesized curve equals `$0.20` (`median`) instead of `$4.16` (`mean`).

**Acceptance Scenarios**:

1. **Given** `rates[:144]` contains a `spike: True` interval whose `renewables` is `68%` (`> 25%`), **When** `RenewablesGuard.evaluate` runs with healthy 12h renewables and Solcast, **Then** `spike_triggered` is `False` and `is_active` is `False`.
2. **Given** `rates[:144]` contains a `spike: True` interval whose `renewables` is `18%` (`<= 25%`), **When** `RenewablesGuard.evaluate` runs (even in `AND` mode with high 12h daytime average renewables), **Then** `spike_triggered` is `True`, `is_active` is `True`, `target_soc` is `100.0`, and the daytime deadline (`16:00` default) is enforced.
3. **Given** 5 historical analog days where 1 day had a `$20.00/kWh` evening spike and 4 days had `$0.20/kWh`, **When** `SyntheticRatesPredictor` synthesizes `pricing_curve` and `export_curve`, **Then** the synthesized value at that step is `$0.20/kWh` (`median`).

---

### Edge Cases

- **Immutable LP Solver Core (`lin_fsm.py`)**: All logic executes strictly as upstream pre-treatment on `rates_timeline`, `RenewablesGuard`, and `SyntheticRatesPredictor`; `custom_components/house_battery_control/fsm/lin_fsm.py` MUST have `0` diff.
- **Negative & Low Tariffs Untouched**: Because `min(price, cap)` only bounds upward spikes (`> $0.35` export / `> $0.60` import), negative solar-sponge feed-in rates (e.g. `-0.06`) and negative wholesale import credits pass through bit-for-bit identical.
- **Runtime Configurability**: `spike_renewables_threshold` (`25.0%` default), `mirage_import_cap` (`$0.60/kWh` default), and `mirage_export_cap` (`$0.35/kWh` default) are configurable in **Options → Control Services** with safe defaults when unset.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Create dedicated upstream pre-treatment module `custom_components/house_battery_control/spike_credibility.py` implementing `pretreat_rates_timeline(rates, now, config)` across three deterministic states per interval:
  - `NEAR_REALTIME` (`lead_mins <= 30.0` or `renewables is None` or `synthetic == True`): prices and `spike` pass through unchanged.
  - `MIRAGE_CLAMPED` (`lead_mins > 30.0` and `renewables > spike_renewables_threshold`, default `25.0%`): `import_price = min(import_price, mirage_import_cap)` (`$0.60` default), `export_price = min(export_price, mirage_export_cap)` (`$0.35` default), and `spike = False`.
  - `CREDIBLE_SCARCITY` (`lead_mins > 30.0` and `renewables <= spike_renewables_threshold`): excess above `mirage_import_cap` / `mirage_export_cap` is weighted by `0.70` (`lead_mins <= 360`) or `0.40` (`lead_mins > 360`), capped at `$1.50` import / `$1.20` export, preserving `spike`.
- **FR-002**: `RatesManager` (`rates.py`) MUST extract unbiased `advanced_price_predicted.predicted` (falling back to `per_kwh` / `value`, removing the `.high` upward substitution), support `time` alongside `start_time`/`periodStart`, and preserve `renewables` on standard Amber forecast intervals whenever present.
- **FR-003**: `RenewablesGuard.evaluate` (`renewables_guard.py`) MUST gate `spike_triggered` so a `spike` interval in `rates[:144]` only triggers the guard when that interval's `renewables is None` or `renewables <= spike_renewables_threshold` (default `25.0%`), setting `target_soc = 100.0` so credible SA scarcity warnings fill the battery completely before the evening peak.
- **FR-004**: `HBCDataUpdateCoordinator._async_update_data` (`coordinator.py`) MUST apply `pretreat_rates_timeline` to `rates.get_rates()` prior to `RenewablesGuard.evaluate`, `_build_solver_inputs`, and diagnostic plan-table rendering so both the LP solver and UI Plan Table share identical pre-treated tariffs.
- **FR-005**: `SyntheticRatesPredictor._average_curves` (`rates_predictor.py`) MUST use `statistics.median` across analog days for `pricing_curve` and `export_curve` to prevent single-day historical spikes from distorting the 24h–48h synthetic tail.
- **FR-006**: Expose `CONF_SPIKE_RENEWABLES_THRESHOLD` (`25.0%`), `CONF_MIRAGE_IMPORT_CAP` (`0.60`), and `CONF_MIRAGE_EXPORT_CAP` (`0.35`) in `const.py`, `config_flow.py` (`Control Services`), `strings.json`, and `translations/en.json`, and document the pre-treatment state machine in `system_requirements.md`.
- **FR-007**: `custom_components/house_battery_control/fsm/lin_fsm.py` MUST NOT be modified (`0` diff).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `100%` of `> 30 min` forecast spikes with `renewables > 25%` are clamped to `<= $0.60` import / `<= $0.35` export and suppressed from triggering `RenewablesGuard`.
- **SC-002**: `100%` of `<= 30 min` imminent spikes pass through uncapped, and `100%` of `> 30 min` spikes with `renewables <= 25%` retain probability-weighted scarcity pricing and activate `100%` SoC daytime pre-charge.
- **SC-003**: Single-day extreme spikes in the 5-day historical analog pool produce `0` outlier distortion on median-aggregated synthetic tariff curves.
- **SC-004**: All Python (`pytest`), JS (`npm test`), and linter (`ruff`, `eslint`) suites pass with `0` lines modified in `lin_fsm.py`.
