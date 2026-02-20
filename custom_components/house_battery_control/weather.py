import logging
from datetime import datetime
from typing import List, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

class WeatherInterval(TypedDict):
    datetime: datetime
    temperature: float
    condition: str

class WeatherManager:
    """Manages fetching weather forecasts."""

    def __init__(self, hass: HomeAssistant, entity_id: str):
        self._hass = hass
        self._entity_id = entity_id
        self._forecast: List[WeatherInterval] = []

    def update(self) -> None:
        """Fetch latest forecast from the weather entity."""
        state = self._hass.states.get(self._entity_id)
        if not state:
            _LOGGER.warning(f"Weather entity {self._entity_id} not found")
            return

        # Standard HA Weather entity "forecast" attribute
        raw_forecast = state.attributes.get("forecast")

        if not raw_forecast:
             # Try new service method if attribute is missing (HA 2023.9+)
             # For now, stick to attribute as it's simpler for initial scaffold
             # and widely supported in custom integrations wrapping APIs.
             # If strictly modern HA, we might need to call `weather.get_forecasts` service.
             _LOGGER.warning(f"No forecast attribute in {self._entity_id}")
             return

        parsed_data = []
        for item in raw_forecast:
            try:
                dt = dt_util.parse_datetime(str(item["datetime"]))
                if not dt:
                    continue

                parsed_data.append({
                    "datetime": dt,
                    "temperature": float(item.get("temperature", 0.0)),
                    "condition": item.get("condition", "unknown")
                })
            except (ValueError, KeyError):
                continue

        parsed_data.sort(key=lambda x: x["datetime"])
        self._forecast = parsed_data

    def get_forecast(self) -> List[WeatherInterval]:
        return self._forecast
