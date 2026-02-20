import logging
from datetime import datetime, timedelta
from typing import List

from homeassistant.core import HomeAssistant

# from .weather import WeatherManager

_LOGGER = logging.getLogger(__name__)

class LoadPredictor:
    """Predicts house load based on history and (optionally) weather."""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        self._history = {} # TODO: implement persistent history storage

    def predict(
        self,
        start_time: datetime,
        temp_forecast: List[dict] = None,
        high_sensitivity: float = 0.0,
        low_sensitivity: float = 0.0,
        high_threshold: float = 25.0,
        low_threshold: float = 15.0,
        duration_hours: int = 24
    ) -> List[float]:
        """
        Predict load for the next N hours in 5-minute intervals.
        Adjusts base load based on temperature forecast.
        """
        intervals = int(duration_hours * 60 / 5)
        prediction = []
        current = start_time

        # Naive lookup for temperature at a given time
        def get_temp_at(target_time: datetime) -> float:
            if not temp_forecast:
                return 20.0 # Standard mild temp
            # Find closest interval in forecast
            closest = temp_forecast[0]
            min_diff = abs((target_time - closest["datetime"]).total_seconds())
            for item in temp_forecast:
                diff = abs((target_time - item["datetime"]).total_seconds())
                if diff < min_diff:
                    min_diff = diff
                    closest = item
            return closest.get("temperature", 20.0)

        for _ in range(intervals):
            hour = current.hour
            # Base Load (Dummy Profile)
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
