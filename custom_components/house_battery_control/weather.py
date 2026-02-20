"""Manages fetching weather forecasts from Home Assistant."""
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

    async def async_update(self) -> None:
        """Fetch latest forecast using HA weather.get_forecasts service (2023.9+)."""
        try:
            # Modern HA method: call the service
            result = await self._hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self._entity_id, "type": "hourly"},
                blocking=True,
                return_response=True,
            )

            if not result or self._entity_id not in result:
                _LOGGER.warning(f"No forecast result for {self._entity_id}")
                # Fallback to attribute
                self._try_attribute_fallback()
                return

            raw_forecast = result[self._entity_id].get("forecast", [])
            self._parse_forecast(raw_forecast)

        except Exception as e:
            _LOGGER.debug(f"Service call failed ({e}), trying attribute fallback")
            self._try_attribute_fallback()

    def _try_attribute_fallback(self) -> None:
        """Fallback: try reading forecast from state attributes (legacy HA)."""
        state = self._hass.states.get(self._entity_id)
        if not state:
            _LOGGER.warning(f"Weather entity {self._entity_id} not found")
            return

        raw_forecast = state.attributes.get("forecast")
        if not raw_forecast:
            _LOGGER.warning(f"No forecast attribute in {self._entity_id}")
            return

        self._parse_forecast(raw_forecast)

    def _parse_forecast(self, raw_forecast: list) -> None:
        """Parse forecast data into WeatherInterval list."""
        parsed_data = []
        for item in raw_forecast:
            try:
                dt = dt_util.parse_datetime(str(item["datetime"]))
                if not dt:
                    continue

                # Ensure timezone-aware (spec 4: TZ safety)
                dt = dt_util.as_utc(dt)

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
