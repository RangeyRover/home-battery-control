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
    ) -> List[dict]:
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

        self.last_history = [{"state": s.state, "last_changed": s.last_changed.isoformat()} for s in historic_states]
        self.last_history_derived = []

        def get_historic_val_at(target_time: datetime) -> float | None:
            """Find the state value at exactly target_time."""
            if not historic_states:
                return None
            selected = None
            for state in historic_states:
                if state.last_changed <= target_time:
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
            past_start = current - timedelta(days=7)
            past_end = past_start + timedelta(minutes=5)
            
            val_start = get_historic_val_at(past_start)
            val_end = get_historic_val_at(past_end)

            # Heuristic: If values are high (e.g. > 10) and increasing, treat as energy kWh
            # If they are low and fluctuant, they might be power kW.
            # But the user explicitly said "correctly dividing for each 5 minute section", 
            # implying we should treat it as energy.
            
            derived_kw = None
            if val_start is not None and val_end is not None:
                if val_end >= val_start:
                    delta = val_end - val_start
                    # If delta is small but the absolute values are large, it's kWh.
                    # 10kW load for 5 mins is ~0.83kWh. 
                    # If delta is < 1.0 but absolute is > 5.0, it's definitely energy derivative.
                    if val_start > 5.0 and delta < 2.0:
                        derived_kw = delta * 12.0
                    else:
                        # Fallback: maybe it IS power? No, let's stick to energy logic if it looks like energy
                        derived_kw = val_start

            if derived_kw is None:
                # Fallback to pure state lookup or dummy profile if same
                hist_val = val_start
                if hist_val is not None:
                    # If it's the 20kW bug, we still have the bug here unless we force division.
                    # Given the user's "insane" comment, we MUST force division if value is high.
                    if hist_val > 5.0:
                         # We don't have a delta, so we guess 0.5kW base or use dummy
                         derived_kw = None 
                    else:
                         derived_kw = hist_val

            if derived_kw is None:
                # Fallback Dummy Profile
                hour = current.hour
                derived_kw = 0.5
                if 17 <= hour <= 21: # Evening Peak
                    derived_kw = 2.5
                elif 7 <= hour <= 9: # Morning Peak
                    derived_kw = 1.5

            # Temperature Adjustment
            temp = get_temp_at(current)
            if temp > high_threshold:
                derived_kw += (temp - high_threshold) * high_sensitivity
            elif temp < low_threshold:
                derived_kw += (low_threshold - temp) * low_sensitivity

            # Round off to 2 decimals for saner display
            kw_final = round(max(0.0, derived_kw), 2)
            prediction.append({"start": current.isoformat(), "kw": kw_final})
            self.last_history_derived.append({
                "start": current.isoformat(), 
                "kw": kw_final,
                "raw_start": val_start,
                "raw_end": val_end
            })
            current += timedelta(minutes=5)

        return prediction
