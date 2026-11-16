# Research: Settlement-Aligned Executor Heartbeat (`064-executor-heartbeat-dispatch`)

## R-01: When Is the AEMO / Amber 5-Minute Settlement Moment?

- **Decision**: Align HBC to **5-minute NEM settlement slots** (`:00, :05, :10, :15, :20, :25, :30, :35, :40, :45, :50, :55`) using **dual settlement triggers**:
  1. **Immediate Tariff Arrival Trigger**: Track state changes on configured price sensors (`CONF_CURRENT_IMPORT_PRICE_ENTITY`, `CONF_CURRENT_EXPORT_PRICE_ENTITY`, `CONF_IMPORT_PRICE_ENTITY`, `CONF_EXPORT_PRICE_ENTITY`) so when **Amber Express** pushes the confirmed 5-minute settlement price via WebSocket/adaptive poll (typically `:XX:05`–`:XX:12`), HBC evaluates immediately.
  2. **Wall-Clock Settlement Fallback (`minute=range(0, 60, 5), second=15`)**: Schedule an aligned clock tick 15 seconds past every 5-minute boundary (`:00:15, :05:15, ..., :55:15`).
- **Rationale**:
  - AEMO 5-minute settlement (5MS) intervals begin on exact 5-minute clock marks (`:00`, `:05`, etc.), NOT relative to when Home Assistant happened to boot (`timedelta(seconds=300)`).
  - However, AEMO + Amber take ~3–12 seconds past `:00` to publish the confirmed 5-minute dispatch price. Firing at `second=0` evaluates stale prices from the prior 5-minute block; firing at `second=15` guarantees the new settlement price is settled in HA (and covers Fixed TOU or unchanged-price intervals where no state-change event fires), while tracking the Amber Express entities triggers even faster (~`:XX:06`) whenever prices update!
  - Because `PowerwallExecutor` deduplicates active renewals by **5-minute settlement slot ID (`int(utc_ts // 300)`)**, if Amber Express already triggered renewal at `11:05:06`, the `11:05:15` clock fallback sees `slot == 11:05` and produces **zero duplicate script calls**!
- **Alternatives considered**:
  - Free-running `270s` monotonic stopwatch: Rejected because it drifts relative to actual `:00/:05/:10` billing boundaries.
  - Firing clock tick at `second=0`: Rejected because AEMO/Amber 5-minute confirmed prices arrive 5–12 seconds after `:00`.

## R-02: Intra-Slot `limit_kw` Drift Suppression Under Local Polling

- **Decision**: Deduplicate same-state calls within the same 5-minute settlement slot (`slot_id = int(utc_now.timestamp() // 300)`) regardless of fractional `limit_kw` changes.
- **Rationale**:
  - Local Powerwall polling updates `sensor.powerwall_2_percentage_charged` every 5–10 seconds, causing `limit_kw` to drift by a few hundredths of a kW mid-slot. Since HA control scripts apply site-level dispatch commands (`-6300 W` / `+10000 W` for `600s`), deduplicating by `(state, settlement_slot)` eliminates sub-interval gateway/logbook chatter while keeping genuine state transitions (`CHARGE_GRID → SELF_CONSUMPTION`, etc.) instantaneous at any second.

## R-03: Preventing Stop-vs-Start Race on Direct Reversals (`CHARGE_GRID ↔ DISCHARGE_GRID`)

- **Decision**: Pass `blocking=True` wrapped in `asyncio.wait_for(..., timeout=15.0)` when executing a transitional stop script prior to starting the opposite dispatch script.
- **Rationale**:
  - `hass.services.async_call("script", "turn_on", ...)` defaults to `blocking=False`. Without awaiting the transitional stop script, `resume_battery_operation` and `allow_export: never` in `Charge Stop` can finish milliseconds *after* `Export Battery` starts, canceling the new export. Bounding the wait to `15.0s` prevents a hung script from stalling the coordinator.
