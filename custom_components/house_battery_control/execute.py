"""Powerwall Executor — translates FSM states into battery commands.

Responsible for:
- Mapping FSM states to HA service calls
- Deduplicating commands (don't re-send if state unchanged)
- Providing a human-readable summary of the last command
"""
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
    CONF_ALLOW_EXPORT_ENTITY,
    STATE_CHARGE_GRID,
    STATE_CHARGE_SOLAR,
    STATE_DISCHARGE_GRID,
    STATE_DISCHARGE_HOME,
    STATE_IDLE,
    STATE_PRESERVE,
)

_LOGGER = logging.getLogger(__name__)

# Command descriptions per state
_STATE_DESCRIPTIONS = {
    STATE_IDLE: "Self-Consumption mode, no grid charging",
    STATE_CHARGE_GRID: "Backup mode, grid charging enabled",
    STATE_CHARGE_SOLAR: "Self-Consumption mode, solar only",
    STATE_DISCHARGE_HOME: "Self-Consumption mode, reserve 0%",
    STATE_DISCHARGE_GRID: "Time-Based mode, export enabled",
    STATE_PRESERVE: "Backup mode, reserve 100%",
}


class PowerwallExecutor:
    """Translates FSM states into Powerwall service calls."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self._hass = hass
        self._config = config
        self._last_state: str | None = None
        self._last_limit: float = 0.0
        self._apply_count: int = 0

    @property
    def last_state(self) -> str | None:
        """Return the last applied state."""
        return self._last_state

    @property
    def apply_count(self) -> int:
        """Return how many times a state change was applied."""
        return self._apply_count

    def apply_state(self, state: str, limit_kw: float) -> None:
        """Apply a new FSM state to the Powerwall.

        Deduplicates: if state and limit haven't changed, no action.
        """
        if state == self._last_state and limit_kw == self._last_limit:
            _LOGGER.debug(f"State unchanged ({state}), skipping apply")
            return

        self._last_state = state
        self._last_limit = limit_kw
        self._apply_count += 1

        _LOGGER.info(f"Applying state: {state} (limit: {limit_kw:.1f} kW)")

        # Queue the actual HA service calls
        # These will be async in production; for now we log the intent.
        self._queue_commands(state, limit_kw)

    def _queue_commands(self, state: str, limit_kw: float) -> None:
        """Determine and log which HA services to call for a given state.

        In production, these would be:
        - switch.turn_on/off for grid charging
        - select.select_option for operation mode
        - number.set_value for backup reserve %
        """
        charge_entity = self._config.get(CONF_ALLOW_CHARGE_FROM_GRID_ENTITY)
        export_entity = self._config.get(CONF_ALLOW_EXPORT_ENTITY)

        if state == STATE_CHARGE_GRID:
            _LOGGER.info(f"CMD: Enable grid charging ({charge_entity})")
            _LOGGER.info(f"CMD: Set operation mode to Backup ({export_entity})")
        elif state == STATE_DISCHARGE_HOME:
            _LOGGER.info(f"CMD: Disable grid charging ({charge_entity})")
            _LOGGER.info(f"CMD: Set operation mode to Self-Consumption ({export_entity})")
        elif state == STATE_PRESERVE:
            _LOGGER.info(f"CMD: Disable grid charging ({charge_entity})")
            _LOGGER.info(f"CMD: Set reserve to 100% ({export_entity})")
        elif state == STATE_CHARGE_SOLAR:
            _LOGGER.info(f"CMD: Disable grid charging ({charge_entity})")
            _LOGGER.info(f"CMD: Set operation mode to Self-Consumption ({export_entity})")
        elif state == STATE_DISCHARGE_GRID:
            _LOGGER.info(f"CMD: Enable export ({export_entity})")
        else:
            # IDLE — neutral
            _LOGGER.info(f"CMD: Self-Consumption, no overrides ({export_entity})")

    def get_command_summary(self) -> str:
        """Return a human-readable summary of the last command."""
        if self._last_state is None:
            return "No command sent yet"
        desc = _STATE_DESCRIPTIONS.get(self._last_state, "Unknown state")
        return f"{self._last_state}: {desc} (limit: {self._last_limit:.1f} kW)"
