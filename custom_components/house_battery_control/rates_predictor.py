import logging
from dataclasses import dataclass
from datetime import datetime

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

@dataclass
class AnalogDay:
    date: datetime
    pv_yield: float
    pricing_curve: list[float]

class SyntheticRatesPredictor:
    """Predicts future pricing by finding historical analog days with similar solar output."""

    def __init__(self, hass: HomeAssistant, solcast_entity_id: str = "sensor.solcast_pv_forecast_tomorrow"):
        self._hass = hass
        self._solcast_entity_id = solcast_entity_id
        self._last_calculated_solar_kwh = None

        self.last_analog_days: list[AnalogDay] = []
        self.synthesized_pricing_curve: list[float] = []

    async def async_check_and_update(self):
        """Check current forecast against last search. Run analog search if drifted > 2 kWh."""
        state = self._hass.states.get(self._solcast_entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return

        try:
            current_forecast = float(state.state)
        except ValueError:
            return

        # Trigger search if we have no prior search, or if drift exceeds 2 kWh
        if (self._last_calculated_solar_kwh is None or
            abs(current_forecast - self._last_calculated_solar_kwh) > 2.0):

            _LOGGER.debug(f"Solcast forecast drifted to {current_forecast} kWh. Triggering analog search.")
            self._last_calculated_solar_kwh = current_forecast

            # Execute the heavy DB queries in the executor thread
            analog_days = await self._hass.async_add_executor_job(
                self._run_analog_search, current_forecast
            )

            self.last_analog_days = analog_days
            self.synthesized_pricing_curve = self._average_pricing_curves(analog_days)

    def _run_analog_search(self, target_kwh: float) -> list[AnalogDay]:
        """Perform SQLite queries to find 5 closest historical days. (Blocking)"""
        # In a real implementation, this would query history.get_significant_states.
        # For Phase 1 TDD, we implement the structure and averaging logic.
        return []

    def _average_pricing_curves(self, analog_days: list[AnalogDay]) -> list[float]:
        """Mathematically average the pricing curves of the given analog days."""
        if not analog_days:
            return []

        # Assuming all curves have the same length (e.g. 48 half-hour blocks or 576 5-min blocks)
        curve_length = len(analog_days[0].pricing_curve)
        if curve_length == 0:
            return []

        averaged = [0.0] * curve_length
        for day in analog_days:
            for i in range(curve_length):
                averaged[i] += day.pricing_curve[i]

        for i in range(curve_length):
            averaged[i] /= len(analog_days)

        return averaged
