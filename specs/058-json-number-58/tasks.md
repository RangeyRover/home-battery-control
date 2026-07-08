# Tasks: 058 - Fix Amber Express Mapping & Solar Guard Refinement

## Phase 1: Implementation
- [x] T001 [US1] Update `strings.json` with clearer `use_amber_express` terminology
- [x] T002 [US1] Update `coordinator.py` to route the `CONF_CURRENT_*` entities to `RatesManager` when Amber Express is active
- [x] T003 [US1] Add a unit test to `tests/test_coordinator.py` to verify Amber Express entity mapping logic

## Dependencies
- All tasks can be executed sequentially.

## Implementation Strategy
- First update `strings.json`.
- Next update `coordinator.py` to map entities correctly.
- Add test coverage.
- Run tests to confirm everything works.
