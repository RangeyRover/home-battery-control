# v1.9.0-beta.18 — Settlement-aligned local dispatch heartbeat

This prerelease updates `PowerwallExecutor` and `HBCDataUpdateCoordinator` (`Feature 064`) to support timed local Powerwall dispatch commands (`teslemetry.dispatch_battery_power` with a 10-minute / `600s` safety duration) aligned to 5-minute NEM / Amber settlement boundaries.

## Highlights

- **5-Minute Settlement-Slot Keepalive (`PowerwallExecutor`):**
  - Active states (`CHARGE_GRID`, `DISCHARGE_GRID`) execute immediately on entry and re-execute **once per new 5-minute settlement slot** (`:00, :05, ..., :55`) to keep `600s` timed local dispatches continuously renewed without mid-session dropouts—while preserving a 10-minute hardware dead-man's switch if Home Assistant goes offline.
  - Suppresses all intra-slot duplicate calls (including `:XX:06` Amber push + `:XX:15` clock tick and fractional `limit_kw` drift from 5–10s local Powerwall SoC updates).
  - Passive states (`SELF_CONSUMPTION`, `ERROR`) remain strictly one-and-done across idle slots.
  - Direct active-to-active reversals (`CHARGE_GRID ↔ DISCHARGE_GRID`) await completion of the previous stop script (`blocking=True`, bounded by `15.0s`) before starting the opposite dispatch so `resume_battery_operation` cannot race and cancel the new dispatch.
- **Settlement Moment Triggers (`HBCDataUpdateCoordinator`):**
  - Subscribes to configured tariff entities (`CONF_CURRENT_IMPORT_PRICE_ENTITY`, `CONF_CURRENT_EXPORT_PRICE_ENTITY`, `CONF_IMPORT_PRICE_ENTITY`, `CONF_EXPORT_PRICE_ENTITY`) so Amber Express settlement updates trigger immediate evaluation.
  - Registers a guaranteed wall-clock settlement tick at `:00:15, :05:15, ..., :55:15` (`DEFAULT_SETTLEMENT_SECOND = 15`, safely after AEMO/Amber's 5–12s settlement publication delay) with clean listener teardown on reload/unload.

## Validation

- Full test suite: `362 passed, 2 xfailed` (`pytest tests/ -q`).
- Linters: `ruff check custom_components/ tests/` and `npm run lint:js` passed with 0 errors and 0 warnings.
- Non-destructive solver check: `0` lines modified in `fsm/lin_fsm.py`.
