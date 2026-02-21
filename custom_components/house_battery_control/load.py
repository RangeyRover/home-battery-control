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
        self.last_history = []

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
        max_load_kw: float = 4.0,
    ) -> List[dict]:
        """
        Predict load for the next N hours in 5-minute intervals.
        Derives kW from kWh deltas with a safety cap.
        Fetches history via the internal HA API and formats it exactly like the REST endpoint.
        """
        intervals = int(duration_hours * 60 / 5)
        prediction = []
        current = start_time

        # Robustly detect if this is an energy sensor (kWh) or power sensor (kW)
        is_energy_sensor = False
        current_state = self._hass.states.get(load_entity_id)
        if current_state:
            unit = current_state.attributes.get("unit_of_measurement", "").lower()
            if "wh" in unit:  # kWh, Wh, mWh
                is_energy_sensor = True

        historic_states_raw = []
        self.last_history_raw = []

        # Fetch history via internal API exactly 5 days up to start_time
        if load_entity_id:
            from homeassistant.components.recorder import history
            import re
            
            end_date = start_time
            start_date = end_date - timedelta(days=5)

            try:
                states_dict = await self._hass.async_add_executor_job(
                    history.get_significant_states, self._hass, start_date, end_date, [load_entity_id]
                )
                historic_states_raw = states_dict.get(load_entity_id, [])
                
                # Format to exact REST API match
                formatted_states = []
                for s in historic_states_raw:
                    formatted_states.append({
                        "entity_id": s.entity_id,
                        "state": s.state,
                        # Preserve exact isoformat with original timezone (like +00:00)
                        # We use .replace(microsecond=0) because standard HA REST API
                        # usually trims microseconds in this endpoint.
                        "last_changed": s.last_changed.replace(microsecond=0).isoformat(),
                        "last_updated": s.last_updated.replace(microsecond=0).isoformat(),
                        "attributes": dict(s.attributes),
                    })

                # REST API returns a list of lists (one per entity)
                if formatted_states:
                    self.last_history_raw = [formatted_states]

            except Exception as e:
                _LOGGER.error(f"Error fetching load history via internal API: {e}")

        # The prediction loop requires the internal list
        historic_states_parsed = self.last_history_raw[0] if self.last_history_raw else []

        # Provide a safe lookup for the prediction logic
        def get_historic_val_at(target_time: datetime) -> float | None:
            """Find the state value at exactly target_time."""
            if not historic_states_parsed:
                return None
            
            from homeassistant.util import dt as dt_util
            selected = None
            for state_dict in historic_states_parsed:
                state_time_str = state_dict.get("last_changed")
                if not state_time_str:
                    continue
                state_time = dt_util.parse_datetime(state_time_str)
                if state_time and state_time <= target_time:
                    selected = state_dict
                else:
                    break
            
            if selected:
                state_val = selected.get("state")
                if state_val not in ("unknown", "unavailable"):
                    try:
                        return float(state_val)
                    except (ValueError, TypeError):
                        pass
            return None

        # Naive lookup for temperature at a given time
        def get_temp_at(target_time: datetime) -> float:
            if not temp_forecast:
                return 20.0  # Standard mild temp
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
            # Base logic uses 5 days ago to match exact interval but averaged or just matched from Day-5?
            # We fetch 5 days. We want the value from 1 day ago to predict today, or 5 days ago?
            # To be safe and use fetched data, let's use current - 1 day (yesterday).
            # The user dataset covers 5 days. We could average them, but simple is best for now given the main goal was REST integration.
            past_start = current - timedelta(days=1)
            past_end = past_start + timedelta(minutes=5)

            val_start = get_historic_val_at(past_start)
            val_end = get_historic_val_at(past_end)

            derived_kw = None
            if val_start is not None and val_end is not None:
                if val_end >= val_start:
                    delta = val_end - val_start
                    if is_energy_sensor:
                        # Cumulative kWh -> Power kW (12 intervals of 5 mins in 1 hour)
                        derived_kw = delta * 12.0
                    else:
                        # Raw kW -> Power kW
                        derived_kw = val_start
                else:
                    # Counter reset
                    derived_kw = val_start

            if derived_kw is None:
                # Fallback to pure state lookup or dummy profile
                hist_val = val_start
                if hist_val is not None:
                    if is_energy_sensor:
                        derived_kw = None
                    else:
                        derived_kw = hist_val

            if derived_kw is None:
                # Fallback Dummy Profile
                hour = current.hour
                derived_kw = 0.5
                if 17 <= hour <= 21:  # Evening Peak
                    derived_kw = 2.5
                elif 7 <= hour <= 9:  # Morning Peak
                    derived_kw = 1.5

            # Temperature Adjustment (Preserved per request)
            temp = get_temp_at(current)
            if temp > high_threshold:
                derived_kw += (temp - high_threshold) * high_sensitivity
            elif temp < low_threshold:
                derived_kw += (low_threshold - temp) * low_sensitivity

            # Round off to 2 decimals + Apply 4kW safety cap
            kw_final = round(max(0.0, min(derived_kw, max_load_kw)), 2)
            
            prediction.append({"start": current.isoformat(), "kw": kw_final})
            current += timedelta(minutes=5)

        return prediction
