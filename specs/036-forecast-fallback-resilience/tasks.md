# Tasks: Forecast Fallback Resilience (BUG-036)

**Branch**: `036-forecast-fallback-resilience`  
**Plan**: [plan.md](file:///c:/Users/markn/OneDrive%20-%20IXL%20Signalling/0-01%20AI%20Programming/AI%20Coding/House%20Battery%20Control/specs/036-forecast-fallback-resilience/plan.md)

## Phase 1: Core Fix

- [x] **T1**: Modify `rates.py` — Add `fallback_import_entity_id` / `fallback_export_entity_id` params to `RatesManager.__init__`. Update `update()` to fall back to general parser when express returns empty. (FR-001, FR-002)
- [x] **T2**: Modify `coordinator.py` — Rewire `RatesManager` construction to pass express entities (`CONF_CURRENT_IMPORT_PRICE_ENTITY` / `CONF_CURRENT_EXPORT_PRICE_ENTITY`) as primary when `use_amber_express=True`, passing general forecast entities as fallback. (FR-001)

## Phase 2: Plan Table Decoupling

- [x] **T3**: Modify `coordinator.py` — Update `_build_diagnostic_plan_table()` to iterate over `max(len(rates), len(future_plan))` instead of just `rates`. Synthesize timestamps when rates are shorter than solver output. (FR-003)

## Phase 3: UI Labels

- [x] **T4**: Modify `translations/en.json` — Clarify labels for `current_import_price_entity` / `current_export_price_entity` to indicate they are the primary 24h source when Express is enabled. (FR-006)

## Phase 4: Tests

- [x] **T5**: Add `test_rates_amber_express_uses_correct_entities` — Verify express entities (not general forecast) are used when `use_amber_express=True`.
- [x] **T6**: Add `test_rates_amber_express_fallback_to_general` — Verify fallback to general parser when express returns empty.
- [x] **T7**: Add `test_rates_amber_express_both_unavailable` — Verify graceful handling when both express and general entities are unavailable.
- [x] **T8**: Add `test_plan_table_renders_with_empty_rates` — Verify 288 rows when `rates=[]` but `future_plan` has 288 entries.
- [x] **T9**: Add `test_plan_table_renders_with_partial_rates` — Verify table extends when rates shorter than future_plan.

## Phase 5: Regression & Commit

- [x] **T10**: Run full test suite — 221 passed, 2 xfailed, 0 failures (216 baseline + 5 new).
- [x] **T11**: Commit all changes with conventional commit message.
