"""Powerwall Executor — translates FSM states into battery commands.

Responsible for:
- Mapping FSM states to HA service calls
- Transition-aware command dispatch (only stop what was started)
- 5-minute settlement-slot keepalive for active states (CHARGE_GRID, DISCHARGE_GRID)
- Suppressing intra-slot duplicate commands (including live limit_kw drift)
- Bounded blocking stop-before-start on direct active-state reversals
- Providing a human-readable summary of the last command
"""

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXECUTOR_KEEPALIVE_ENABLED,
    CONF_OBSERVATION_MODE,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    DEFAULT_EXECUTOR_KEEPALIVE_ENABLED,
    DEFAULT_STOP_SCRIPT_TIMEOUT,
    STATE_CHARGE_GRID,
    STATE_DISCHARGE_GRID,
    STATE_ERROR,
    STATE_SELF_CONSUMPTION,
)

_LOGGER = logging.getLogger(__name__)

# Command descriptions per state
_STATE_DESCRIPTIONS = {
    STATE_CHARGE_GRID: "Grid charging enabled",
    STATE_DISCHARGE_GRID: "Grid export enabled",
    STATE_SELF_CONSUMPTION: "Self-Consumption mode, inverter manages autonomously",
    STATE_ERROR: "Error state, all actions stopped",
}

_ACTIVE_STATES = frozenset({STATE_CHARGE_GRID, STATE_DISCHARGE_GRID})


def _current_settlement_slot() -> int:
    """Return the discrete 5-minute NEM/UTC settlement slot index."""
    return int(dt_util.utcnow().timestamp() // 300)


class PowerwallExecutor:
    """Translates FSM states into Powerwall service calls."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self._hass = hass
        self._config = config
        # Requested state (always updated — for dashboard display)
        self._last_state: str | None = None
        self._last_limit: float = 0.0
        # Executed state (only updated after successful command — for dedup & keepalive)
        self._last_executed_state: str | None = None
        self._last_executed_limit: float = 0.0
        self._last_executed_slot: int | None = None
        self._apply_count: int = 0

    @property
    def last_state(self) -> str | None:
        """Return the last requested state (for dashboard)."""
        return self._last_state

    @property
    def last_executed_state(self) -> str | None:
        """Return the last actually executed state (for diagnostics)."""
        return self._last_executed_state

    @property
    def apply_count(self) -> int:
        """Return how many times a state change or keepalive was applied."""
        return self._apply_count

    async def apply_state(self, state: str, limit_kw: float) -> None:
        """Apply a new FSM state (or 5-minute settlement keepalive) to the Powerwall.

        Always updates requested state for dashboard display.
        Active states (CHARGE_GRID, DISCHARGE_GRID) re-execute once per new 5-minute
        settlement slot to keep timed local dispatches alive while suppressing intra-slot
        telemetry/SoC refreshes. Passive states remain strictly one-and-done.
        Observation mode suppresses execution without updating executed state.
        """
        # Always update requested state (dashboard can show what FSM wants)
        self._last_state = state
        self._last_limit = limit_kw

        # Observation mode: track request but do not execute
        if self._config.get(CONF_OBSERVATION_MODE, False):
            _LOGGER.info(f"Observation mode — suppressing: {state} (limit: {limit_kw:.1f} kW)")
            return

        current_slot = _current_settlement_slot()

        # Same-state deduplication & 5-minute settlement-slot keepalive
        if state == self._last_executed_state:
            if state not in _ACTIVE_STATES:
                _LOGGER.debug(f"Passive state unchanged ({state}), skipping execute")
                return
            keepalive_enabled = bool(
                self._config.get(
                    CONF_EXECUTOR_KEEPALIVE_ENABLED, DEFAULT_EXECUTOR_KEEPALIVE_ENABLED
                )
            )
            if not keepalive_enabled or current_slot == self._last_executed_slot:
                _LOGGER.debug(
                    f"Active state unchanged in settlement slot {current_slot} ({state}), skipping execute"
                )
                return
            _LOGGER.info(
                f"Settlement keepalive renewal for {state} (slot {current_slot}, limit: {limit_kw:.1f} kW)"
            )
        else:
            _LOGGER.info(f"Applying state: {state} (limit: {limit_kw:.1f} kW)")

        self._apply_count += 1

        # Execute the actual HA service calls
        await self._async_execute_commands(state, limit_kw)

        # Only update executed state & slot AFTER successful execution
        self._last_executed_state = state
        self._last_executed_limit = limit_kw
        self._last_executed_slot = current_slot

    async def _async_execute_commands(self, state: str, limit_kw: float) -> None:
        """Determine and invoke which HA services to call for a given state.

        Transition-aware: only stops the previously active command.
        Uses _last_executed_state to know what was running.
        On direct active-to-active reversals, awaits the stop script (bounded by
        DEFAULT_STOP_SCRIPT_TIMEOUT) before invoking the opposite start script.
        """
        charge_script = self._config.get(CONF_SCRIPT_CHARGE)
        charge_stop_script = self._config.get(CONF_SCRIPT_CHARGE_STOP)
        discharge_script = self._config.get(CONF_SCRIPT_DISCHARGE)
        discharge_stop_script = self._config.get(CONF_SCRIPT_DISCHARGE_STOP)

        async def _call(
            entity_id: str | None, intent: str, *, wait_for_completion: bool = False
        ) -> None:
            if not entity_id:
                _LOGGER.info(f"CMD: {intent} (skipped: no script configured)")
                return
            _LOGGER.info(f"CMD: {intent} ({entity_id})")
            if wait_for_completion:
                try:
                    await asyncio.wait_for(
                        self._hass.services.async_call(
                            "script", "turn_on", {"entity_id": entity_id}, blocking=True
                        ),
                        timeout=DEFAULT_STOP_SCRIPT_TIMEOUT,
                    )
                except TimeoutError:
                    _LOGGER.warning(
                        "Timed out after %.1fs waiting for stop script %s; proceeding with new state",
                        DEFAULT_STOP_SCRIPT_TIMEOUT,
                        entity_id,
                    )
            else:
                await self._hass.services.async_call(
                    "script", "turn_on", {"entity_id": entity_id}
                )

        prev = self._last_executed_state

        if state == STATE_CHARGE_GRID:
            # Stop discharge if it was running, then start/renew charge
            if prev == STATE_DISCHARGE_GRID:
                await _call(
                    discharge_stop_script,
                    "Stop discharge (transition to charge)",
                    wait_for_completion=True,
                )
            await _call(charge_script, "Enable grid charging")

        elif state == STATE_DISCHARGE_GRID:
            # Stop charge if it was running, then start/renew discharge
            if prev == STATE_CHARGE_GRID:
                await _call(
                    charge_stop_script,
                    "Stop charge (transition to discharge)",
                    wait_for_completion=True,
                )
            await _call(discharge_script, "Enable grid export")

        elif state == STATE_SELF_CONSUMPTION:
            # Stop only what was previously active
            if prev == STATE_CHARGE_GRID:
                await _call(charge_stop_script, "Stop charge (entering self-consumption)")
            elif prev == STATE_DISCHARGE_GRID:
                await _call(discharge_stop_script, "Stop discharge (entering self-consumption)")
            # If prev was already SELF_CONSUMPTION or None, no calls needed

        elif state == STATE_ERROR:
            # Safety: stop whatever is active
            if prev == STATE_CHARGE_GRID:
                await _call(charge_stop_script, "Stop charge (error state)")
            elif prev == STATE_DISCHARGE_GRID:
                await _call(discharge_stop_script, "Stop discharge (error state)")

        else:
            _LOGGER.warning(f"Unknown state '{state}', no commands issued")

    def get_command_summary(self) -> str:
        """Return a human-readable summary of the last command."""
        if self._last_state is None:
            return "No command sent yet"
        desc = _STATE_DESCRIPTIONS.get(self._last_state, "Unknown state")
        return f"{self._last_state}: {desc} (limit: {self._last_limit:.1f} kW)"
