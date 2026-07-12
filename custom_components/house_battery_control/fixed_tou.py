import logging
from datetime import datetime, time, timedelta
from typing import Any, List

from .const import (
    CONF_FIXED_TOU_IMPORT_START,
    CONF_FIXED_TOU_IMPORT_END,
    CONF_FIXED_TOU_IMPORT_PRICE,
    CONF_FIXED_TOU_EXPORT_START,
    CONF_FIXED_TOU_EXPORT_END,
    CONF_FIXED_TOU_EXPORT_PRICE,
)

_LOGGER = logging.getLogger(__name__)

class FixedTOUGenerator:
    """Generates a 48-hour forward-looking array of pricing blocks based on Fixed TOU configuration.
    Mimics the Amber Electric forecast JSON structure so downstream logic remains unchanged."""

    def __init__(self, config_data: dict[str, Any]):
        """Initialize the FixedTOUGenerator with configuration data."""
        self._config = config_data
        
        # Pre-parse periods for O(1) lookups during generation
        self._import_periods = self._parse_periods(
            CONF_FIXED_TOU_IMPORT_START, 
            CONF_FIXED_TOU_IMPORT_END, 
            CONF_FIXED_TOU_IMPORT_PRICE
        )
        self._export_periods = self._parse_periods(
            CONF_FIXED_TOU_EXPORT_START, 
            CONF_FIXED_TOU_EXPORT_END, 
            CONF_FIXED_TOU_EXPORT_PRICE
        )

    def _parse_periods(self, start_prefix: str, end_prefix: str, price_prefix: str) -> list[dict[str, Any]]:
        periods = []
        for i in range(1, 11):
            start_str = self._config.get(start_prefix.format(i))
            end_str = self._config.get(end_prefix.format(i))
            price_val = self._config.get(price_prefix.format(i))
            
            if start_str and end_str and price_val is not None:
                periods.append({
                    "start": self._parse_time(start_str),
                    "end": self._parse_time(end_str),
                    "price": float(price_val)
                })
        return periods

    def generate_forecast(self, start_time: datetime) -> List[dict[str, Any]]:
        """Generate exactly 48 hours of 5-minute pricing blocks starting from start_time."""
        forecast = []

        current_time = start_time
        end_time = start_time + timedelta(hours=48)
        chunk_duration = timedelta(minutes=5)

        while current_time < end_time:
            local_time = current_time.time()

            import_price = self._get_price_for_time(local_time, self._import_periods, default=0.0)
            export_price = self._get_price_for_time(local_time, self._export_periods, default=0.0)

            next_time = current_time + chunk_duration

            block = {
                "start_time": current_time,
                "end_time": next_time,
                "per_kwh": import_price,
                "export_price": export_price,
                "type": "FORECAST"
            }
            forecast.append(block)

            current_time = next_time

        return forecast

    def _get_price_for_time(self, t: time, periods: list[dict[str, Any]], default: float) -> float:
        """Determine price for a given local time from a list of periods."""
        for period in periods:
            if self._time_in_range(period["start"], period["end"], t):
                return period["price"]
        return default

    def _parse_time(self, time_str: str) -> time:
        """Parse a time string (HH:MM:SS) into a datetime.time object."""
        if not time_str:
            return time(0, 0)
        try:
            parts = time_str.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            s = int(parts[2]) if len(parts) > 2 else 0
            return time(h, m, s)
        except ValueError:
            return time(0, 0)

    def _time_in_range(self, start: time, end: time, x: time) -> bool:
        """Return true if x is in the range [start, end).
        Handles midnight wrap-around if start > end."""
        if start == time(0, 0) and end == time(0, 0):
            return True
            
        # end time(0,0) actually means midnight of the next day, which is equivalent to 24:00
        # For comparisons where start is anything else and end is 00:00, we should treat x < end as True if end is next day midnight
        # But time(0,0) is less than any other time, so start <= end is False. 
        # Wait, if end == time(0,0) and start != time(0,0), it goes to the else block (start <= x or x < end)
        # x < time(0,0) is False. So it's just start <= x. This is correct for times before midnight!

        if start < end:
            return start <= x < end
        else:
            return start <= x or x < end
