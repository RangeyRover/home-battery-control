# Tasks: Settlement-Aligned Executor Heartbeat for Timed Powerwall Dispatch

**Input**: Design documents from `/specs/064-executor-heartbeat-dispatch/`  
**Prerequisites**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Phase 1: Setup & Baseline

- [x] T001 Create branch `064-executor-heartbeat-dispatch`, [spec.md](spec.md), [research.md](research.md), [plan.md](plan.md), and update `system_requirements.md` §3.6.
- [x] T002 Run baseline `pytest tests/test_execute.py tests/test_coordinator.py -q` after plan approval (`61 passed`).

---

## Phase 2: Tests First (RED) — US1, US2, US3

- [x] T003 [P] [US1] Add settlement-slot keepalive renewal tests in `tests/test_execute.py`.
- [x] T004 [P] [US2] Add intra-slot suppression tests (`:05:06` + `:05:15` + `limit_kw` drift) & mid-slot transition tests in `tests/test_execute.py`.
- [x] T005 [P] [US3] Add passive-state multi-slot one-and-done dedup, `executor_keepalive_enabled=False` opt-out, observation-mode multi-slot suppression, and direct-reversal (`CHARGE_GRID ↔ DISCHARGE_GRID`) `blocking=True` + timeout safety tests in `tests/test_execute.py`.
- [x] T006 [P] [US1] Add coordinator settlement trigger tests in `tests/test_coordinator.py`.
- [x] T007 Run `pytest tests/test_execute.py tests/test_coordinator.py -v` and confirm new tests fail (`9 failed` — RED confirmed).

---

## Phase 3: Implementation (GREEN) — US1, US2, US3

- [x] T008 [US1] Add `CONF_EXECUTOR_KEEPALIVE_ENABLED`, `DEFAULT_EXECUTOR_KEEPALIVE_ENABLED = True`, `DEFAULT_SETTLEMENT_SECOND = 15`, and `DEFAULT_STOP_SCRIPT_TIMEOUT = 15.0` to `custom_components/house_battery_control/const.py`.
- [x] T009 [US1] [US2] [US3] Implement 5-minute settlement-slot keepalive (`_last_executed_slot`), intra-slot suppression, passive-state one-and-done dedup, and bounded `blocking=True` reversal stop calls in `custom_components/house_battery_control/execute.py`.
- [x] T010 [US1] Add tariff entity state tracking, `async_start_settlement_clock()` (`minute=range(0, 60, 5), second=15`), and `async_unload()` listener cleanup in `custom_components/house_battery_control/coordinator.py` and wire setup/unload in `custom_components/house_battery_control/__init__.py`.
- [x] T011 Run `pytest tests/test_execute.py tests/test_coordinator.py -q` and verify all tests pass (`70 passed` — GREEN confirmed).

---

## Phase 4: Cross-Cutting Verification & Polish

- [x] T012 [P] Update execution & cadence documentation in `docs/how-it-works.md`.
- [x] T013 Run full regression & lint suite (`pytest tests/ -q` -> `362 passed, 2 xfailed` and `ruff check custom_components/ tests/` -> `All checks passed!`) and verify `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is empty.
