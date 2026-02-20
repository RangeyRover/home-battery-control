import logging
from datetime import datetime
from typing import List, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

class RateInterval(TypedDict):
    start: datetime
    end: datetime
    price: float # c/kWh
    type: str # ACTUAL or FORECAST

class RatesManager:
    """Manages fetching and processing tariff rates."""

    def __init__(self, hass: HomeAssistant, entity_id: str):
        self._hass = hass
        self._entity_id = entity_id
        self._rates: List[RateInterval] = []

    def update(self) -> None:
        """Fetch latest rates from the sensor."""
        state = self._hass.states.get(self._entity_id)
        if not state:
            _LOGGER.warning(f"Tariff entity {self._entity_id} not found")
            return

        # Amber Electric Sensor exposes 'future_prices' and 'current_price'
        # We handle the 'variable_intervals' or 'future_prices' attribute
        raw_data = state.attributes.get("future_prices") or state.attributes.get("variable_intervals")

        if not raw_data:
            _LOGGER.warning(f"No future_prices found in {self._entity_id}")
            return

        parsed_rates = []
        for interval in raw_data:
            try:
                # Parse timestamps (ISO 8601)
                start_ts = dt_util.parse_datetime(interval["periodStart"])
                end_ts = dt_util.parse_datetime(interval["periodEnd"])

                if not start_ts or not end_ts:
                    continue

                # Amber prices are often in c/kWh directly or $/kWh.
                # The schema example shows 25.5 (c/kWh). We assume c/kWh.
                price = float(interval.get("perKwh", 0))

                parsed_rates.append({
                    "start": start_ts,
                    "end": end_ts,
                    "price": price,
                    "type": interval.get("periodType", "UNKNOWN")
                })
            except (ValueError, KeyError) as e:
                _LOGGER.error(f"Error parsing rate interval: {e}")
                continue

        # Sort by start time
        parsed_rates.sort(key=lambda x: x["start"])
        self._rates = parsed_rates
        _LOGGER.debug(f"Loaded {len(self._rates)} rate intervals")

    def get_rates(self) -> List[RateInterval]:
        """Return the processed list of rates."""
        return self._rates

    def get_price_at(self, time: datetime) -> float:
        """Get the price for a specific time."""
        for rate in self._rates:
            if rate["start"] <= time < rate["end"]:
                return rate["price"]
        return 0.0 # Default or fallback?
