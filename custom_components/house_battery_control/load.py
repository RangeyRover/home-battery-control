import logging
from datetime import datetime, timedelta
from typing import Any, List

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class LoadPredictor:
    """Predicts house load based on history and (optionally) weather."""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        self.last_history_raw: list[list[dict]] = []
        self.last_history: list[dict] = []

    async def async_predict(
        self,
        start_time: datetime,
        temp_forecast: List[Any] | None = None,
        high_sensitivity: float = 0.0,
        low_sensitivity: float = 0.0,
        high_threshold: float = 25.0,
        low_threshold: float = 15.0,
        duration_hours: int = 24,
        load_entity_id: str | None = None,
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
        if not load_entity_id:
            return []

        # Get history for the specified duration
        state = self._hass.states.get(load_entity_id)
        is_energy_sensor = False
        if state:
            unit = state.attributes.get("unit_of_measurement", "").lower()
            if "wh" in unit:  # kWh, Wh, mWh
                is_energy_sensor = True

        historic_states_raw = []
        if not getattr(self, "testing_bypass_history", False):
            self.last_history_raw = []

        # Fetch history via internal API exactly 5 days up to start_time
        if load_entity_id and not getattr(self, "testing_bypass_history", False):
            from homeassistant.components.recorder import history

            end_date = start_time
            start_date = end_date - timedelta(days=5)

            try:
                states_dict = await self._hass.async_add_executor_job(
                    history.get_significant_states,
                    self._hass,
                    start_date,
                    end_date,
                    [load_entity_id],
                )
                historic_states_raw = states_dict.get(load_entity_id, [])

                # Format to exact REST API match
                formatted_states = []
                for s in historic_states_raw:
                    formatted_states.append(
                        {
                            "entity_id": s.entity_id,  # type: ignore
                            "state": s.state,  # type: ignore
                            # Preserve exact isoformat with original timezone (like +00:00)
                            # We use .replace(microsecond=0) because standard HA REST API
                            # usually trims microseconds in this endpoint.
                            "last_changed": s.last_changed.replace(microsecond=0).isoformat(),  # type: ignore
                            "last_updated": s.last_updated.replace(microsecond=0).isoformat(),  # type: ignore
                            "attributes": dict(s.attributes),  # type: ignore
                        }
                    )

                # REST API returns a list of lists (one per entity)
                if formatted_states:
                    self.last_history_raw = [formatted_states]

            except Exception as e:
                _LOGGER.error(f"Error fetching load history via internal API: {e}")

        # The prediction loop requires the internal list
        historic_states_parsed = self.last_history_raw[0] if self.last_history_raw else []

        # Build statistical 24hr forecast if data exists using the native user module
        from .historical_analyzer import build_historical_profile, extract_valid_data

        valid_data = extract_valid_data(historic_states_parsed)

        # Build Profile
        # User requested exact alignment natively with extract script
        target_tz = start_time.tzinfo if start_time.tzinfo else None
        historical_profile = build_historical_profile(valid_data, target_tz, is_energy_sensor)

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

        # Track previous legitimate usage for midnight anomaly bridging
        # (Fallback loop preserved for missing slots)

        for _ in range(intervals):
            time_slot = current.strftime("%H:%M")
            derived_kw = None

            if time_slot in historical_profile:
                if is_energy_sensor:
                    derived_kw = historical_profile[time_slot] * 12.0
                else:
                    derived_kw = historical_profile[time_slot]

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
