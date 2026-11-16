# Implementation Plan: Settlement-Aligned Executor Heartbeat for Timed Powerwall Dispatch

**Branch**: `064-executor-heartbeat-dispatch` | **Date**: 2026-11-16 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/064-executor-heartbeat-dispatch/spec.md`

## Summary

Align HBC's 5-minute evaluation and local Powerwall command renewal to **AEMO / Amber 5-minute settlement boundaries (`:00`, `:05`, `:10`, ..., `:55`)**:
1. **`HBCDataUpdateCoordinator` Settlement Triggers**: Track configured import/export price sensors so Amber Express settlement price updates (~`:XX:06`) trigger immediate evaluation, backed by a wall-clock settlement listener at **`:00:15`, `:05:15`, ..., `:55:15`** (`DEFAULT_SETTLEMENT_SECOND = 15`, safely after AEMO's 5–12s publication delay) with clean unload/reload cleanup.
2. **`PowerwallExecutor` 5-Minute Settlement-Slot Keepalive**: Replace permanent "one-and-done" active-state deduplication with **once-per-5-minute-settlement-slot (`int(utc_now.timestamp() // 300)`)** renewal for `CHARGE_GRID` and `DISCHARGE_GRID` (keeping `600s` timed local dispatches continuously alive with ~5 minutes of overlap), while suppressing all mid-slot telemetry/SoC refreshes, keeping `SELF_CONSUMPTION` and `ERROR` strictly one-and-done, and awaiting transitional stop scripts (`blocking=True`, `15s` timeout) on direct `CHARGE_GRID ↔ DISCHARGE_GRID` reversals.

## Technical Context

**Language/Version**: Python 3.12+ (Home Assistant Custom Integration)  
**Primary Dependencies**: Home Assistant Core (`async_track_time_change`, `async_track_state_change_event`, `dt_util`), Python `asyncio`  
**Storage**: N/A (in-memory `_last_executed_slot: int | None` inside `PowerwallExecutor`)  
**Testing**: `pytest`, `pytest-asyncio`, `ruff`  
**Target Platform**: Home Assistant 2026.11+ (with local Teslemetry Powerwall control & Amber Express / Fixed TOU)  
**Project Type**: Home Assistant Custom Integration (`custom_components/house_battery_control`)  
**Constraints**: Zero changes to `fsm/lin_fsm.py`; preserve all existing `test_coordinator.py` & `test_execute.py` mock contracts; clean listener unsubscribe on unload/reload  
**Scale/Scope**: 4 source files (`const.py`, `execute.py`, `coordinator.py`, `__init__.py`), 2 unit test files (`tests/test_execute.py`, `tests/test_coordinator.py`), 2 docs (`system_requirements.md`, `docs/how-it-works.md`)

## Gate Check

| Gate | Status | Notes |
|------|--------|-------|
| `spec.md` & `system_requirements.md` updated before code | PASS | `specs/064-executor-heartbeat-dispatch/spec.md` & `system_requirements.md` §3.6 written |
| Non-destructive to `lin_fsm.py` | PASS | Zero changes to `fsm/lin_fsm.py` |
| Observation Mode preserved | PASS | `CONF_OBSERVATION_MODE` suppresses both transitions and settlement renewals |
| TDD (RED before GREEN) | PASS | Enforced in `tasks.md` Phase 2 prior to touching production `.py` files |

## Proposed Changes

### 1. Constants (`custom_components/house_battery_control/const.py`)
- `CONF_EXECUTOR_KEEPALIVE_ENABLED = "executor_keepalive_enabled"`
- `DEFAULT_EXECUTOR_KEEPALIVE_ENABLED = True`
- `DEFAULT_SETTLEMENT_SECOND = 15` *(15 seconds past `:00, :05, ..., :55` — safely after AEMO/Amber's 3–12s settlement publication latency)*
- `DEFAULT_STOP_SCRIPT_TIMEOUT = 15.0`

### 2. Settlement-Slot Executor (`custom_components/house_battery_control/execute.py`)
- Helper `_current_settlement_slot() -> int`: returns `int(dt_util.utcnow().timestamp() // 300)` (discrete 5-minute UTC settlement bucket — note all Australian timezones including `+10:00`, `+10:30` Adelaide, and `+11:00` align on exact 5-minute boundaries relative to UTC!).
- Track `self._last_executed_slot: int | None = None`.
- In `PowerwallExecutor.apply_state(state, limit_kw)`:
  1. Always update `self._last_state = state` and `self._last_limit = limit_kw`.
  2. If `CONF_OBSERVATION_MODE` is `True`: log and return without updating `_last_executed_*`.
  3. Compute `current_slot = _current_settlement_slot()`.
  4. When `state == self._last_executed_state`:
     - If `state not in {STATE_CHARGE_GRID, STATE_DISCHARGE_GRID}` (`SELF_CONSUMPTION` or `ERROR`): return (strictly one-and-done).
     - If `not self._config.get(CONF_EXECUTOR_KEEPALIVE_ENABLED, DEFAULT_EXECUTOR_KEEPALIVE_ENABLED)` or `current_slot == self._last_executed_slot`: return (suppresses both rapid 5–10s telemetry refreshes, fractional `limit_kw` drift, AND the `:XX:15` clock tick if Amber Express already renewed at `:XX:06`!).
     - Otherwise (`current_slot != self._last_executed_slot`): log settlement keepalive renewal and proceed to execute!
  5. Increment `self._apply_count`, call `await self._async_execute_commands(state, limit_kw)`, and record `_last_executed_state = state`, `_last_executed_limit = limit_kw`, `_last_executed_slot = current_slot`.
- In `PowerwallExecutor._async_execute_commands`:
  - On direct reversals (`CHARGE_GRID ↔ DISCHARGE_GRID`), invoke the transitional stop script with `blocking=True` inside `asyncio.wait_for(..., timeout=DEFAULT_STOP_SCRIPT_TIMEOUT)` (logging a warning on `TimeoutError` and continuing to the start script).
  - On settlement keepalive renewals (`prev == state`), `prev` is not the opposite active state, so only the active start script is called.

### 3. Settlement Triggers in Coordinator & Setup (`coordinator.py`, `__init__.py`)
- In `HBCDataUpdateCoordinator.__init__`:
  - Store `self._unsub_listeners: list[Callable[[], None]] = []`.
  - Add `CONF_CURRENT_IMPORT_PRICE_ENTITY`, `CONF_CURRENT_EXPORT_PRICE_ENTITY`, `CONF_IMPORT_PRICE_ENTITY`, and `CONF_EXPORT_PRICE_ENTITY` (deduplicated while preserving order) to `telemetry_entities` so Amber Express settlement price updates trigger `_async_on_state_change` immediately, and append the returned unsubscribe callable to `self._unsub_listeners`.
- Add `HBCDataUpdateCoordinator.async_start_settlement_clock(self) -> None`:
  - Registers `async_track_time_change(self.hass, self._async_on_settlement_tick, minute=range(0, 60, 5), second=DEFAULT_SETTLEMENT_SECOND)` and appends the unsubscribe callable to `self._unsub_listeners`.
- Add `@callback def async_unload(self) -> None` on `HBCDataUpdateCoordinator` to unsubscribe all registered listeners cleanly.
- In `__init__.py`:
  - Call `coordinator.async_start_settlement_clock()` in `async_setup_entry` (after first refresh) and `coordinator.async_unload()` in `async_unload_entry`.

## Verification Plan

1. **Phase 2 (RED)**: Add unit tests in `tests/test_execute.py` and `tests/test_coordinator.py` and run `pytest tests/test_execute.py tests/test_coordinator.py -v` to confirm RED failure.
2. **Phase 3 (GREEN)**: Implement changes in `const.py`, `execute.py`, `coordinator.py`, and `__init__.py`; verify `pytest tests/test_execute.py tests/test_coordinator.py -v` passes (GREEN).
3. **Phase 4 (Full Suite)**: Run `pytest tests/ -q` and `ruff check custom_components/ tests/` and confirm `git diff custom_components/house_battery_control/fsm/lin_fsm.py` is empty.
