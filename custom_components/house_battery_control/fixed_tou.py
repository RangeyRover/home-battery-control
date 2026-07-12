import logging
from datetime import datetime, time, timedelta
from typing import Any, List

_LOGGER = logging.getLogger(__name__)

class FixedTOUGenerator:
    """Generates a 48-hour forward-looking array of pricing blocks based on Fixed TOU configuration.
    Mimics the Amber Electric forecast JSON structure so downstream logic remains unchanged."""

    def __init__(self, config_data: dict[str, Any]):
        """Initialize the FixedTOUGenerator with configuration data."""
        self._config = config_data

    def generate_forecast(self, start_time: datetime) -> List[dict[str, Any]]:
        """Generate exactly 48 hours of 5-minute pricing blocks starting from start_time."""
        forecast = []

        # We need to evaluate times based on the local timezone to handle DST correctly.
        # start_time is assumed to be timezone-aware.
        current_time = start_time
        end_time = start_time + timedelta(hours=48)

        chunk_duration = timedelta(minutes=5)

        while current_time < end_time:
            # We must evaluate the local time (accounting for DST shifts if any)
            local_time = current_time.time()

            price = self._get_price_for_time(local_time)

            next_time = current_time + chunk_duration

            block = {
                "start_time": current_time,
                "end_time": next_time,
                "per_kwh": price,
                "type": "FORECAST"
            }
            forecast.append(block)

            current_time = next_time

        return forecast

    def _get_price_for_time(self, t: time) -> float:
        """Determine if a given local time falls into Peak, Off-Peak, or Shoulder."""

        peak_start = self._parse_time(self._config.get("fixed_tou_peak_start", "16:00:00"))
        peak_end = self._parse_time(self._config.get("fixed_tou_peak_end", "20:00:00"))
        peak_price = float(self._config.get("fixed_tou_peak_price", 40.0))

        offpeak_start = self._parse_time(self._config.get("fixed_tou_offpeak_start", "00:00:00"))
        offpeak_end = self._parse_time(self._config.get("fixed_tou_offpeak_end", "06:00:00"))
        offpeak_price = float(self._config.get("fixed_tou_offpeak_price", 10.0))

        shoulder_price = float(self._config.get("fixed_tou_shoulder_price", 20.0))

        if self._time_in_range(peak_start, peak_end, t):
            return peak_price

        if self._time_in_range(offpeak_start, offpeak_end, t):
            return offpeak_price

        return shoulder_price

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
        if start <= end:
            return start <= x < end
        else:
            return start <= x or x < end
