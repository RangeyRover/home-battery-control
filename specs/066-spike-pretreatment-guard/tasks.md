# Tasks: Upstream Spike Credibility Pre-Treatment State Machine & Renewables-Gated Spike Guard

**Input**: Design documents from `/specs/066-spike-pretreatment-guard/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `system_requirements.md`

## Phase 1: Setup & Specification

- [x] T001 Create feature branch `066-spike-pretreatment-guard` and author `specs/066-spike-pretreatment-guard/spec.md`
- [x] T002 Validate specification quality in `specs/066-spike-pretreatment-guard/checklists/requirements.md`
- [x] T003 Update `system_requirements.md` (§4.4 & §4.5) with Pre-Treatment State Machine & Renewables Guard rules
- [x] T004 Author technical design and research in `specs/066-spike-pretreatment-guard/research.md` and `specs/066-spike-pretreatment-guard/plan.md`

---

## Phase 2: User Story 1 & 2 - Pre-Treatment State Machine & Unbiased Amber Parsing (Priority: P1) 🎯 MVP

**Goal**: Isolate the 3-state spike pre-treatment machine (`NEAR_REALTIME`, `MIRAGE_CLAMPED`, `CREDIBLE_SCARCITY`) in `spike_credibility.py` and remove `.high` tail-risk inflation in `rates.py`.

**Independent Test**: Verify `pretreat_rates_timeline` clamps `> 30m` high-renewables (`> 25%`) spikes to `$0.60` / `$0.35` (`spike=False`), leaves `<= 30m` spikes uncapped, applies `0.70×` / `0.40×` scarcity weights when `renewables <= 25%`, leaves negative tariffs and `None` renewables untouched, and `RatesManager` uses unbiased `predicted`.

### Tests for US1 & US2 (TDD RED)

- [x] T005 [P] [US1] Create `tests/test_spike_credibility.py` covering `MIRAGE_CLAMPED`, `NEAR_REALTIME`, `CREDIBLE_SCARCITY` (`<= 6h` and `> 6h`), negative tariffs, `renewables=None`, and custom caps
- [x] T006 [P] [US1] Add tests in `tests/test_rates.py` verifying unbiased `advanced_price_predicted.predicted` (no `.high` inflation at low renewables), `time`/`value` fallback, and optional `renewables` extraction in standard Amber

### Implementation for US1 & US2 (TDD GREEN)

- [x] T007 [US1] Add spike pre-treatment constants and defaults in `custom_components/house_battery_control/const.py`
- [x] T008 [US1] Implement `pretreat_rates_timeline` state machine in `custom_components/house_battery_control/spike_credibility.py`
- [x] T009 [US2] Update `_parse_amber_express_entity` and `_parse_entity` in `custom_components/house_battery_control/rates.py`

---

## Phase 3: User Story 3 - Renewables-Gated Spike Guard, Median Analog Tail & Coordinator Wiring (Priority: P1)

**Goal**: Gate `RenewablesGuard.spike_triggered` on interval `renewables <= 25%` (`target_soc = 100.0`), switch `SyntheticRatesPredictor` price curves to `median`, wire `pretreat_rates_timeline` into `coordinator.py`, and expose config controls in `Control Services`.

**Independent Test**: Verify `RenewablesGuard` ignores `spike=True` at `renewables=68%` and activates `100%` SoC daytime pre-charge at `renewables=18%`; verify `SyntheticRatesPredictor` rejects single-day `$20` analog outliers; verify coordinator & config flow end-to-end.

### Tests for US3 (TDD RED)

- [x] T010 [P] [US3] Update/add high-renewables suppression and low-renewables (`<= 25%`) `100%` SoC spike tests in `tests/test_renewables_guard.py`
- [x] T011 [P] [US3] Add single-day spike outlier median test in `tests/test_rates_predictor.py`
- [x] T012 [P] [US3] Update/add coordinator pre-treatment + renewables-gated spike tests in `tests/test_coordinator.py` and options persistence test in `tests/test_config_flow.py`

### Implementation for US3 (TDD GREEN)

- [x] T013 [P] [US3] Gate `spike_triggered` on `renewables <= spike_renewables_threshold` and set `target_soc = 100.0` in `custom_components/house_battery_control/renewables_guard.py`
- [x] T014 [P] [US3] Use `statistics.median` for `pricing_curve` and `export_curve` in `custom_components/house_battery_control/rates_predictor.py`
- [x] T015 [US3] Wire `pretreat_rates_timeline` and `spike_renewables_threshold` into `custom_components/house_battery_control/coordinator.py`
- [x] T016 [US3] Expose `spike_renewables_threshold`, `mirage_import_cap`, and `mirage_export_cap` in `custom_components/house_battery_control/config_flow.py`, `strings.json`, and `translations/en.json`

---

## Phase 4: Polish & Cross-Cutting Verification

- [x] T017 Run full `pytest tests/ -q`, `npm test`, `ruff check custom_components/ tests/`, `npm run lint:js`, and verify zero diff on `custom_components/house_battery_control/fsm/lin_fsm.py`
- [x] T018 Bump `manifest.json` & `hacs.json` to `1.9.0-beta.20` and record validation in `specs/066-spike-pretreatment-guard/validation.md`
