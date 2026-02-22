"""Solar forecast provider that reads from Solcast HA integration entities.

Instead of calling the Solcast API directly, this reads data from
the Solcast PV Solar integration for Home Assistant:
https://github.com/BJReplay/ha-solcast-solar

Expected entities:
- sensor.solcast_pv_forecast_today (with 'detailedForecast' attribute)
- sensor.solcast_pv_forecast_tomorrow (with 'detailedForecast' attribute)
"""

import logging
from datetime import timedelta
from typing import List

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .base import SolarForecastData, SolarForecastProvider

_LOGGER = logging.getLogger(__name__)

# Default Solcast entity IDs from the HA integration
DEFAULT_FORECAST_TODAY = "sensor.solcast_pv_forecast_today"
DEFAULT_FORECAST_TOMORROW = "sensor.solcast_pv_forecast_tomorrow"


class SolcastSolar(SolarForecastProvider):
    """Reads solar forecast from Solcast HA integration entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        forecast_today_entity: str = DEFAULT_FORECAST_TODAY,
        forecast_tomorrow_entity: str = DEFAULT_FORECAST_TOMORROW,
    ):
        self._hass = hass
        self._forecast_today_entity = forecast_today_entity
        self._forecast_tomorrow_entity = forecast_tomorrow_entity

    async def async_get_forecast(self) -> List[SolarForecastData]:
        """Read forecast from Solcast HA entities."""
        result: list[SolarForecastData] = []

        for entity_id in [self._forecast_today_entity, self._forecast_tomorrow_entity]:
            state = self._hass.states.get(entity_id)
            if not state:
                _LOGGER.warning(f"Solcast entity {entity_id} not found")
                continue

            # Solcast HA integration stores detailed data in 'detailedForecast'
            # or 'forecast' attribute depending on version
            detailed = (
                state.attributes.get("detailedForecast")
                or state.attributes.get("detailed_forecast")
                or state.attributes.get("forecasts")
            )

            if not detailed:
                _LOGGER.debug(
                    f"No detailed forecast in {entity_id}, "
                    f"available attrs: {list(state.attributes.keys())}"
                )
                continue

            for item in detailed:
                try:
                    # Parse period start/end
                    period_start = dt_util.parse_datetime(
                        str(item.get("period_start") or item.get("period_end", ""))
                    )
                    if not period_start:
                        continue

                    # Ensure timezone-aware (spec 4: TZ safety)
                    period_start = dt_util.as_utc(period_start)

                    # pv_estimate is in kW (mean power over period)
                    pv_kw = float(item.get("pv_estimate", 0))

                    # Get period duration (default 30 min)
                    period_str = item.get("period", "PT30M")
                    duration_mins = 30
                    if "PT" in str(period_str) and "M" in str(period_str):
                        try:
                            duration_mins = int(str(period_str).replace("PT", "").replace("M", ""))
                        except ValueError:
                            pass

                    # Create 5-min slots (block interpolation)
                    slots = max(1, duration_mins // 5)
                    for i in range(slots):
                        slot_time = period_start + timedelta(minutes=i * 5)
                        result.append(
                            {
                                "start": slot_time,
                                "kw": pv_kw,
                            }
                        )

                except (ValueError, KeyError, TypeError) as e:
                    _LOGGER.error(f"Error parsing Solcast interval: {e}")
                    continue

        # Sort by start time and deduplicate
        result.sort(key=lambda x: x["start"])
        _LOGGER.debug(f"Loaded {len(result)} solar forecast slots from Solcast entities")
        return result
