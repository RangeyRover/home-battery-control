import logging
from datetime import datetime, timedelta
from typing import List

from homeassistant.components.recorder import history
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class LoadPredictor:
    """Predicts house load based on history and (optionally) weather."""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def async_predict(
        self,
        start_time: datetime,
        temp_forecast: List[dict] = None,
        high_sensitivity: float = 0.0,
        low_sensitivity: float = 0.0,
        high_threshold: float = 25.0,
        low_threshold: float = 15.0,
        duration_hours: int = 24,
        load_entity_id: str = None,
    ) -> List[float]:
        """
        Predict load for the next N hours in 5-minute intervals.
        Adjusts base load based on temperature forecast.
        """
        intervals = int(duration_hours * 60 / 5)
        prediction = []
        current = start_time

        # Fetch history from 7 days ago if entity is provided
        historic_states = []
        if load_entity_id:
            past_start = start_time - timedelta(days=7)
            # Add some buffer to ensure we cover the whole period
            past_end = past_start + timedelta(hours=duration_hours + 1)

            states_dict = await self._hass.async_add_executor_job(
                history.get_significant_states,
                self._hass, past_start, past_end, [load_entity_id]
            )
            historic_states = states_dict.get(load_entity_id, [])

        def get_historic_load_at(target_past_time: datetime) -> float | None:
            if not historic_states:
                return None

            selected = None
            for state in historic_states:
                if state.last_changed <= target_past_time:
                    selected = state
                else:
                    break

            if selected and selected.state not in ("unknown", "unavailable"):
                try:
                    return float(selected.state)
                except (ValueError, TypeError):
                    pass
            return None

        # Naive lookup for temperature at a given time
        def get_temp_at(target_time: datetime) -> float:
            if not temp_forecast:
                return 20.0 # Standard mild temp
            # Find closest interval in forecast
            closest = temp_forecast[0]
            if "datetime" in closest:
                min_diff = abs((target_time - closest["datetime"]).total_seconds())
            else:
                min_diff = float("inf")
            for item in temp_forecast:
                if "datetime" in item:
                    diff = abs((target_time - item["datetime"]).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        closest = item
            return closest.get("temperature", 20.0)

        for _ in range(intervals):
            past_time = current - timedelta(days=7)
            hist_val = get_historic_load_at(past_time)

            if hist_val is not None:
                val = hist_val
            else:
                # Fallback Base Load (Dummy Profile) if no history is available
                hour = current.hour
                val = 0.5
                if 17 <= hour <= 21: # Evening Peak
                    val = 2.5
                elif 7 <= hour <= 9: # Morning Peak
                    val = 1.5

            # Temperature Adjustment
            temp = get_temp_at(current)
            if temp > high_threshold:
                val += (temp - high_threshold) * high_sensitivity
            elif temp < low_threshold:
                val += (low_threshold - temp) * low_sensitivity

            prediction.append(max(0.0, val)) # Never negative load
            current += timedelta(minutes=5)

        return prediction
