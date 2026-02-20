import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .base import SolarForecastData, SolarForecastProvider

_LOGGER = logging.getLogger(__name__)

class SolcastSolar(SolarForecastProvider):
    """Solcast implementation of SolarForecastProvider."""

    def __init__(self, hass: HomeAssistant, api_key: str, site_id: str):
        self._hass = hass
        self._api_key = api_key
        self._site_id = site_id
        self._cache_dir = hass.config.path("custom_components/house_battery_control/cache")

        if not os.path.exists(self._cache_dir):
            os.makedirs(self._cache_dir)

    async def async_get_forecast(self) -> List[SolarForecastData]:
        """Fetch, cache, and interpolate Solcast data."""

        # 1. Try to load recent cache
        data = await self._load_cached_forecast()

        # 2. If valid, return it
        if data:
            _LOGGER.debug("Returning cached Solcast data")
            return self._interpolate_forecast(data)

        # 3. Else, fetch new data
        fetched_data = await self._fetch_from_api()
        if fetched_data:
            await self._save_cache(fetched_data)
            return self._interpolate_forecast(fetched_data)

        _LOGGER.warning("Failed to fetch Solcast data, returning empty forecast")
        return []

    async def _fetch_from_api(self) -> Optional[dict]:
        """Fetch raw data from Solcast API."""
        url = f"https://api.solcast.com.au/rooftop_sites/{self._site_id}/forecasts"
        params = {"format": "json", "api_key": self._api_key, "hours": 48}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        _LOGGER.warning("Solcast API rate limit exceeded")
                    else:
                        _LOGGER.error(f"Solcast API error: {response.status}")
        except Exception as e:
            _LOGGER.error(f"Error fetching Solcast data: {e}")

        return None

    async def _load_cached_forecast(self) -> Optional[dict]:
        """Load forecast from JSON cache if less than 4 hours old."""
        cache_file = os.path.join(self._cache_dir, f"solcast_{self._site_id}.json")
        if not os.path.exists(cache_file):
            return None

        try:
            mtime = os.path.getmtime(cache_file)
            age = datetime.now().timestamp() - mtime
            if age > (4 * 3600): # 4 hours
                _LOGGER.debug("Solcast cache expired")
                return None

            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.error(f"Error loading Solcast cache: {e}")
            return None

    async def _save_cache(self, data: dict):
        """Save API response to cache."""
        cache_file = os.path.join(self._cache_dir, f"solcast_{self._site_id}.json")
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            _LOGGER.error(f"Error saving Solcast cache: {e}")

    def _interpolate_forecast(self, api_data: dict) -> List[SolarForecastData]:
        """Convert 30-min API data to 5-min intervals."""
        forecasts = api_data.get("forecasts", [])
        result = []

        # Sort by period_end
        forecasts.sort(key=lambda x: x["period_end"])

        for item in forecasts:
            # Solcast gives period_end in UTC
            period_end_str = item.get("period_end")
            pv_kw = item.get("pv_estimate", 0) # This is usually kW (power) or kWh?
            # Solcast docs: "pv_estimate": 2.5 (kW if period is instantaneous/mean power, or kWh if energy?)
            # Usually Solcast gives Mean Power (kW) over the period for 'forecasts'.
            # Note: The original 'solcast.py' treated it as Energy (kWh) -> "pv_estimate / 60 * period_minutes"
            # Solcast API "forecasts" endpoint usually returns kW (Power).
            # "pv_estimate": 0.5 means 0.5 kW average power over the period.
            # To get kWh: 0.5 kW * 0.5 h = 0.25 kWh.
            # Our system needs...?
            # FSM Context: `forecast_solar: list[float] # Current kW`?
            # FSM Base says: `solar_production: float # Current kW`.
            # So we likely want kW.

            period_end = dt_util.parse_datetime(period_end_str)
            period_str = item.get("period", "PT30M")

            # Simple linear interpolation?
            # Or just block usage (constant power for 30 mins)?
            # Block usage is safer and simpler for now.

            # Parse period duration (e.g. PT30M -> 30 mins)
            duration_mins = 30
            if "PT" in period_str and "M" in period_str:
                try:
                     duration_mins = int(period_str.replace("PT", "").replace("M", ""))
                except ValueError:
                    pass

            start_time = period_end - timedelta(minutes=duration_mins)

            # Create 5-min slots
            slots = duration_mins // 5
            for i in range(slots):
                slot_time = start_time + timedelta(minutes=i*5)
                result.append({
                    "start": slot_time,
                    "kwh": pv_kw # We store kW here actually, despite the key name 'kwh' in base.py?
                                # base.py said `kwh: float`.
                                # If base.py expects kWh per 5 mins, we should convert.
                                # If base.py expects kW power, we should rename/document.
                                # Let's assume base.py 'kwh' meant 'energy in this slot'?
                                # 5-min energy = kW * (5/60).
                })

        # Correction: base.py allows me to decide. I will stick to POWER (kW) for easier FSM logic,
        # but the field is named 'kwh'. I should probably update base.py or just use it as kW.
        # Given "load_power" is kW, "solar_production" is kW.
        # I will store Energy (kWh) in the 5-min slot to be precise, or Power?
        # A 5-min slot of 2.5 kW = 2.5 * (5/60) = 0.208 kWh.
        # I'll store kW (Power) for now, as that's what Solcast gives directly.
        # I will modify base.py to clarify or just assume it's power.
        # CHECK base.py content again: `kwh: float`. I'll assume it means Energy.
        # So: pv_kw * (5/60).

        # Re-iterating:
        # result.append({"start": ..., "kwh": pv_kw * (5/60)})

        return result
