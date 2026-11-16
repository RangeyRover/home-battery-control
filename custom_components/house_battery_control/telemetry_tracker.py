"""Telemetry Cost Tracker for House Battery Control.

Implements Feature 031: Dedicated Cumulative Cost Telemetry Tracker.
Decouples billing accuracy from predictive solver execution rates.
"""

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

from .const import (
    CONF_EXPORT_TODAY_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_TRACKER_EXPORT_PRICE,
    CONF_TRACKER_IMPORT_PRICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.cumulative_cost_v2"
STORAGE_VERSION = 1


class TelemetryCostTracker:
    """Independent tracker for cumulative grid cost based on exact 5-min intervals."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the tracker."""
        self.hass = hass
        self.config = config
        self.cumulative_cost: float = 0.0
        self._last_import: float | None = None
        self._last_export: float | None = None

        # Keep memory of prices to defend against API drops (Spec req: Resiliency to Gaps)
        self._last_price_import: float | None = None
        self._last_price_export: float | None = None

        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._unsub_tick = None

    async def async_load(self) -> None:
        """Load historical data from storage and start the tick clock."""
        data = await self._store.async_load()
        if data:
            self.cumulative_cost = data.get("cumulative_cost", 0.0)
            self._last_import = data.get("last_import")
            self._last_export = data.get("last_export")
            self._last_price_import = data.get("last_price_import")
            self._last_price_export = data.get("last_price_export")
            _LOGGER.debug(
                "Loaded TelemetryCostTracker: cost=$%.2f, last_import=%s, last_export=%s",
                self.cumulative_cost,
                self._last_import,
                self._last_export,
            )
        else:
            _LOGGER.debug("No previous TelemetryCostTracker data found, starting fresh.")

        # Subscribe to exactly the 5-minute boundaries
        self._unsub_tick = async_track_time_change(
            self.hass, self._on_tick, minute=range(0, 60, 5), second=0
        )

    @callback
    def async_unload(self) -> None:
        """Clean up the tracker."""
        if self._unsub_tick:
            self._unsub_tick()
            self._unsub_tick = None

    async def _on_tick(self, time: Any) -> None:
        """Calculate the cost delta over the last 5 minutes."""
        raw_import_today_id = self.config.get(CONF_IMPORT_TODAY_ENTITY)
        raw_export_today_id = self.config.get(CONF_EXPORT_TODAY_ENTITY)
        price_import_id = self.config.get(CONF_TRACKER_IMPORT_PRICE)
        price_export_id = self.config.get(CONF_TRACKER_EXPORT_PRICE)

        if not all([raw_import_today_id, raw_export_today_id, price_import_id, price_export_id]):
            _LOGGER.debug("TelemetryCostTracker skip: Required sensor(s) missing from config.")
            return

        state_imp = self.hass.states.get(raw_import_today_id)
        state_exp = self.hass.states.get(raw_export_today_id)
        state_price_imp = self.hass.states.get(price_import_id)
        state_price_exp = self.hass.states.get(price_export_id)

        if not all([state_imp, state_exp, state_price_imp, state_price_exp]):
            _LOGGER.debug("TelemetryCostTracker skip: One or more entities not found in state machine.")
            return

        try:
            current_import = float(state_imp.state)
            current_export = float(state_exp.state)
        except ValueError:
            _LOGGER.warning("TelemetryCostTracker skip: kWh values non-numeric.")
            return

        # Handle Prices & Gap Resiliency
        current_price_imp = None
        if state_price_imp.state not in ("unavailable", "unknown"):
            try:
                current_price_imp = float(state_price_imp.state)
                self._last_price_import = current_price_imp
            except ValueError:
                pass

        if current_price_imp is None:
            if self._last_price_import is not None:
                current_price_imp = self._last_price_import
            else:
                _LOGGER.debug("No valid import price and no fallback available.")
                return

        current_price_exp = None
        if state_price_exp.state not in ("unavailable", "unknown"):
            try:
                current_price_exp = float(state_price_exp.state)
                self._last_price_export = current_price_exp
            except ValueError:
                pass

        if current_price_exp is None:
            if self._last_price_export is not None:
                current_price_exp = self._last_price_export
            else:
                _LOGGER.debug("No valid export price and no fallback available.")
                return

        # Delta calculation with Midnight Reset Interpolation logic
        import_delta = 0.0
        export_delta = 0.0

        if self._last_import is not None:
            if current_import < self._last_import:
                # Midnight reset: Assume the new base current_import is the total delta for this segment
                import_delta = current_import
            else:
                import_delta = current_import - self._last_import

        if self._last_export is not None:
            if current_export < self._last_export:
                # Midnight reset
                export_delta = current_export
            else:
                export_delta = current_export - self._last_export

        if self._last_import is not None and self._last_export is not None:
            # Multiply and accumulate
            self.cumulative_cost += (import_delta * current_price_imp) - (export_delta * current_price_exp)

            # Persist if changed
            if import_delta > 0 or export_delta > 0:
                self._store.async_delay_save(self._data_to_save, 10.0)

        # Update memories
        self._last_import = current_import
        self._last_export = current_export

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return data of cost tracking to store in a file."""
        return {
            "cumulative_cost": self.cumulative_cost,
            "last_import": self._last_import,
            "last_export": self._last_export,
            "last_price_import": self._last_price_import,
            "last_price_export": self._last_price_export,
        }
