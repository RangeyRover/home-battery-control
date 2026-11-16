# Feature Specification: Settlement-Aligned Executor Heartbeat for Timed Powerwall Dispatch

**Feature Branch**: `064-executor-heartbeat-dispatch`  
**Created**: 2026-11-16  
**Status**: Ready for Planning  
**Input**: User description: "Align 5-minute executor heartbeat and coordinator evaluation to the 5-minute NEM/Amber settlement boundaries for timed local Powerwall dispatch scripts"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Settlement-Aligned Renewal of Timed Charge & Export Dispatches (Priority: P1)

As the battery system owner on 5-minute wholesale settlement (AEMO / Amber Electric) using timed local battery dispatch commands (`600s` / 10-minute safety duration), I need House Battery Control to evaluate each 5-minute settlement block (`:00`, `:05`, `:10`, ..., `:55`) as soon as the confirmed settlement price arrives (with a `:XX:15` wall-clock guarantee) and re-trigger the active Charge or Discharge script once per 5-minute settlement slot so dispatches never expire mid-session, while automatically failing safe within 10 minutes if Home Assistant goes offline.

**Why this priority**: AEMO dispatches 5-minute settlement blocks on `:00, :05, :10, ..., :55` boundaries, with confirmed Amber/AEMO prices typically arriving 5–12 seconds after the boundary. Aligning coordinator ticks and active-state script renewals directly to each 5-minute settlement slot eliminates clock drift, ensures decisions use fresh settlement prices, and keeps a 10-minute hardware timeout continuously renewed with ~5 minutes of overlap.

**Independent Test**: Simulate an active `CHARGE_GRID` or `DISCHARGE_GRID` state across consecutive 5-minute settlement slots (`11:00`, `11:05`, `11:10`) and verify the active script executes once on entry and once in each subsequent 5-minute settlement slot without invoking stop commands in between.

**Acceptance Scenarios**:

1. **Given** the system enters `CHARGE_GRID` or `DISCHARGE_GRID` during the `11:00` settlement slot (`11:00:00–11:04:59`), **When** subsequent settlement slots `11:05` and `11:10` evaluate to the same active state, **Then** the active script is re-executed once in `11:05` and once in `11:10` so a `600s` timed local dispatch never drops out.
2. **Given** configured Amber import/export price entities update ~5–12 seconds after a 5-minute boundary (or the `:XX:15` settlement clock tick fires), **When** the coordinator refreshes, **Then** HBC immediately solves with the new settlement price and applies the state for that 5-minute block.
3. **Given** the system is actively charging or discharging, **When** Home Assistant stops running or loses LAN connectivity, **Then** no further renewals occur and the Powerwall hardware reverts to self-consumption when its `600s` timer expires.

---

### User Story 2 - Intra-Interval Telemetry Chatter Suppression (Priority: P1)

As the system owner with local Powerwall telemetry updating every 5–10 seconds, I need HBC to suppress duplicate Charge or Discharge script calls within the same 5-minute settlement slot—even when minor State-of-Charge updates slightly alter `limit_kw`—so the battery gateway and Home Assistant logbook are not flooded with commands every few seconds.

**Why this priority**: Local gateway polling updates battery power, solar power, grid power, and SoC every 5–10 seconds, triggering coordinator refreshes. Deduplicating same-state active dispatches by 5-minute settlement slot (`floor(utc_timestamp / 300)`) guarantees at most one renewal per 5-minute settlement block while keeping state transitions instantaneous.

**Independent Test**: Trigger repeated same-state `CHARGE_GRID` / `DISCHARGE_GRID` updates within the same 5-minute settlement slot (e.g., `11:05:06`, `11:05:15`, `11:07:30`, `11:09:50`, with varying `limit_kw`) and verify zero duplicate script calls occur until `11:10:00+`.

**Acceptance Scenarios**:

1. **Given** `CHARGE_GRID` has already been executed in the `11:05` settlement slot, **When** live telemetry refreshes at `11:05:15` (scheduled clock tick), `11:06:20`, and `11:09:45` still resolve to `CHARGE_GRID` (even with minor `limit_kw` drift), **Then** zero duplicate Charge script calls are made during the remainder of the `11:05` slot.
2. **Given** `CHARGE_GRID` was executed at `11:05:06`, **When** a mid-slot price spike or SoC change at `11:05:12` causes the solver to switch state to `SELF_CONSUMPTION` or `DISCHARGE_GRID`, **Then** the state transition executes **immediately** without waiting for `11:10`.

---

### User Story 3 - Passive State One-and-Done & Ordered Transitions (Priority: P1)

As the system owner, when HBC is in `SELF_CONSUMPTION` or `ERROR`, stop commands must remain strictly one-and-done across all future 5-minute settlement slots, and direct reversals between `CHARGE_GRID` and `DISCHARGE_GRID` must finish stopping the previous direction before starting the new direction.

**Why this priority**: Repeating stop scripts every 5 minutes when idle would create log noise and notifications, and non-blocking stop-then-start calls can race (`resume_battery_operation` canceling the newly issued `dispatch_battery_power`).

**Independent Test**: Hold `SELF_CONSUMPTION` across multiple 5-minute settlement slots and verify zero repeat calls; transition directly `CHARGE_GRID → DISCHARGE_GRID` and verify the stop call completes (`blocking=True`) before the discharge call is issued.

**Acceptance Scenarios**:

1. **Given** the system transitions from `CHARGE_GRID` to `SELF_CONSUMPTION` in slot `11:05`, **When** `SELF_CONSUMPTION` persists across slots `11:10`, `11:15`, and beyond, **Then** `Charge Stop` is called once on transition and never repeated.
2. **Given** the system is in `CHARGE_GRID`, **When** it transitions directly to `DISCHARGE_GRID`, **Then** the executor awaits `Charge Stop` (`blocking=True`, bounded by a `15s` timeout) before invoking `Discharge`.
3. **Given** Observation Mode is enabled, **When** `CHARGE_GRID` or `DISCHARGE_GRID` is requested across multiple 5-minute settlement slots, **Then** all executions remain suppressed, and disabling Observation Mode immediately executes the active state on the next update.

---

### Edge Cases

- **AEMO / Amber Settlement Latency (`+5s` to `+12s` past `:00/:05/...`)**: Scheduled settlement ticks run at **`second=15`** (`:00:15`, `:05:15`, `:10:15`, ..., `:55:15`) rather than `second=0` so AEMO/Amber dispatch prices have already settled in Home Assistant—while tracking the Amber price entities directly triggers even earlier (e.g. `:05:06`) the instant Amber Express pushes the confirmed settlement price, without double-executing at `:05:15` because both belong to slot `11:05`!
- **Mid-Slot Entry (e.g., `11:04:50`) Followed by `:05:15` Settlement Tick**: Entering `CHARGE_GRID` at `11:04:50` records slot `11:00`; at `11:05:15` (`slot = 11:05`), the executor cleanly syncs onto the `11:05` settlement boundary and marches once per 5-minute block thereafter.
- **Unresponsive Stop Script on Reversal**: Bounded by `DEFAULT_STOP_SCRIPT_TIMEOUT = 15.0` seconds (`asyncio.wait_for`) so the coordinator never hangs indefinitely.
- **Clean Unload / Reload**: Both state-change listeners and the `:XX:15` settlement clock listener MUST unsubscribe cleanly when the integration reloads or unloads.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `PowerwallExecutor` MUST group wall-clock UTC time into discrete 5-minute settlement slots (`int(utc_now.timestamp() // 300)`) and, when the requested state is an active dispatch state (`CHARGE_GRID` or `DISCHARGE_GRID`) matching `last_executed_state`, re-execute the active script once whenever the current 5-minute settlement slot differs from `last_executed_slot` (unless `executor_keepalive_enabled` is explicitly set `False`).
- **FR-002**: Within the same 5-minute settlement slot (`current_slot == last_executed_slot`), `PowerwallExecutor` MUST suppress duplicate executions for the same state—even when `limit_kw` drifts due to live SoC updates.
- **FR-003**: For passive/safe states (`SELF_CONSUMPTION` and `ERROR`), `PowerwallExecutor` MUST NOT re-execute stop commands across subsequent 5-minute settlement slots while the state remains unchanged.
- **FR-004**: Any state transition (`state != last_executed_state`) MUST execute immediately regardless of settlement slot, updating `last_executed_state` and `last_executed_slot` upon completion.
- **FR-005**: During a direct active-to-active reversal (`CHARGE_GRID ↔ DISCHARGE_GRID`), `PowerwallExecutor` MUST await completion of the previous state's stop script (`blocking=True`, bounded by a `15.0s` timeout) before invoking the new state's start script.
- **FR-006**: `HBCDataUpdateCoordinator` MUST:
  1. Include configured tariff entities (`CONF_CURRENT_IMPORT_PRICE_ENTITY`, `CONF_CURRENT_EXPORT_PRICE_ENTITY`, `CONF_IMPORT_PRICE_ENTITY`, `CONF_EXPORT_PRICE_ENTITY`) in its state-change tracking list so Amber Express settlement price arrivals trigger immediate evaluation, and
  2. Register a settlement-aligned wall-clock listener at `minute=range(0, 60, 5), second=15` (`DEFAULT_SETTLEMENT_SECOND = 15`) with clean unsubscribe on entry unload/reload.
- **FR-007**: Observation Mode (`observation_mode = True`) MUST continue to suppress all executions without updating `last_executed_state` or `last_executed_slot`.
- **FR-008**: `system_requirements.md` (§3.6) MUST document the 5-minute settlement-slot keepalive and `:XX:15` / tariff-update settlement trigger behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Active `CHARGE_GRID` and `DISCHARGE_GRID` sessions execute exactly `1` renewal per 5-minute settlement block (`:00, :05, :10, ..., :55`) after initial entry, maintaining `100%` continuity on `600s` timed local dispatches.
- **SC-002**: Sub-interval telemetry refreshes (every `5–10s`) and simultaneous Amber Express push (`:05:06`) + `:05:15` clock ticks produce `0` duplicate script executions within the same 5-minute settlement block.
- **SC-003**: Idle `SELF_CONSUMPTION` and `ERROR` states produce `0` repeat stop calls across subsequent 5-minute settlement blocks.
- **SC-004**: `100%` of existing and new unit tests pass with zero modifications to `lin_fsm.py`.
