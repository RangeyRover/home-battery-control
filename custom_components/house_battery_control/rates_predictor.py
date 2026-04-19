import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components.recorder import history
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

@dataclass
class AnalogDay:
    date: datetime
    pv_yield: float
    pricing_curve: list[float]  # Import price
    export_curve: list[float]
    load_curve: list[float]

class SyntheticRatesPredictor:
    """Predicts future pricing by finding historical analog days with similar solar output."""

    def __init__(
        self,
        hass: HomeAssistant,
        solcast_entity_id: str = "sensor.solcast_pv_forecast_tomorrow",
        import_price_entity_id: str = "",
        export_price_entity_id: str = "",
        load_entity_id: str = "",
    ):
        self._hass = hass
        self._solcast_entity_id = solcast_entity_id
        self._import_price_entity_id = import_price_entity_id
        self._export_price_entity_id = export_price_entity_id
        self._load_entity_id = load_entity_id
        self._last_calculated_solar_kwh = None

        self.last_analog_days: list[AnalogDay] = []
        self.synthesized_pricing_curve: list[float] = []
        self.synthesized_export_curve: list[float] = []
        self.synthesized_load_curve: list[float] = []

    async def async_get_synthetic_outlook(self):
        """Update and return the generated synthetic curves."""
        await self.async_check_and_update()
        return (
            self.last_analog_days,
            self.synthesized_pricing_curve,
            self.synthesized_export_curve,
            self.synthesized_load_curve,
        )

    async def async_check_and_update(self):
        """Check current forecast against last search. Run analog search if drifted > 2 kWh."""
        state = self._hass.states.get(self._solcast_entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return

        try:
            current_forecast = float(state.state)
        except ValueError:
            return

        # Trigger search if we have no prior search, or if drift exceeds 2 kWh
        if (self._last_calculated_solar_kwh is None or
            abs(current_forecast - self._last_calculated_solar_kwh) > 2.0):

            _LOGGER.debug(f"Solcast forecast drifted to {current_forecast} kWh. Triggering analog search.")
            self._last_calculated_solar_kwh = current_forecast

            # Execute the heavy DB queries in the executor thread
            analog_days = await self._hass.async_add_executor_job(
                self._run_analog_search, current_forecast
            )

            self.last_analog_days = analog_days
            self.synthesized_pricing_curve = self._average_curves(analog_days, "pricing_curve")
            self.synthesized_export_curve = self._average_curves(analog_days, "export_curve")
            self.synthesized_load_curve = self._average_curves(analog_days, "load_curve")

    def _normalize_to_288(self, states: list, start_date: datetime) -> list[float]:
        """Convert a list of HA states into a normalized 288-step array (5-min intervals)."""
        curve = [0.0] * 288
        if not states:
            return curve

        current_val = 0.0
        # Find initial value before start_date if available
        for state in reversed(states):
            if state.last_changed < start_date and state.state not in ("unknown", "unavailable", None, ""):
                try:
                    current_val = float(state.state)
                    break
                except ValueError:
                    pass

        state_idx = 0
        num_states = len(states)

        for step in range(288):
            step_time = start_date + timedelta(minutes=step * 5)

            # Advance to the last state that changed before or exactly at step_time
            while state_idx < num_states:
                next_state = states[state_idx]
                if next_state.last_changed <= step_time:
                    if next_state.state not in ("unknown", "unavailable", None, ""):
                        try:
                            current_val = float(next_state.state)
                        except ValueError:
                            pass
                    state_idx += 1
                else:
                    break

            curve[step] = current_val

        return curve

    def _get_lts_curve(self, entity_id: str, day_start: datetime, day_end: datetime) -> list[float]:
        """Retrieve the 5-minute curve from LTS statistics."""
        stats = statistics_during_period(
            self._hass,
            day_start,
            day_end,
            [entity_id],
            "5minute",
            None,
            {"mean", "state"}
        )
        rows = stats.get(entity_id, [])
        curve = [0.0] * 288

        # Map the rows to 5-min intervals
        for row in rows:
            row_start = dt_util.utc_from_timestamp(row["start"]) if isinstance(row["start"], (int, float)) else row["start"]
            if row_start >= day_start and row_start < day_end:
                step = int((row_start - day_start).total_seconds() / 300)
                if 0 <= step < 288:
                    val = row.get("mean")
                    if val is None:
                        val = row.get("state")
                    if val is not None:
                        curve[step] = val

        # Forward-fill any empty gaps in the curve
        current_val = 0.0
        for i in range(288):
            if curve[i] != 0.0:
                current_val = curve[i]
            else:
                curve[i] = current_val
        return curve

    def _run_analog_search(self, target_kwh: float) -> list[AnalogDay]:
        """Perform SQLite queries to find 5 closest historical days. (Blocking)"""
        end_date = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=365)

        daily_yields = {}

        # 1. Query past 365 days of Solcast predictions using Long Term Statistics
        lts_stats = statistics_during_period(
            self._hass,
            start_date,
            end_date,
            [self._solcast_entity_id],
            "hour",
            None,
            {"state", "mean", "max"}
        )
        lts_rows = lts_stats.get(self._solcast_entity_id, [])
        for row in lts_rows:
            # For hour statistics, take max forecast for that day
            row_start = dt_util.utc_from_timestamp(row["start"]) if isinstance(row["start"], (int, float)) else row["start"]
            forecast_date = (row_start + timedelta(days=1)).date()
            if forecast_date < end_date.date():
                val = row.get("max") or row.get("mean") or row.get("state")
                if val is not None:
                    daily_yields[forecast_date] = max(val, daily_yields.get(forecast_date, 0))

        # Fallback to history if LTS is empty (e.g. no state_class)
        if not daily_yields:
            solcast_states_dict = history.get_significant_states(
                self._hass,
                start_date,
                end_date,
                entity_ids=[self._solcast_entity_id],
            )
            solcast_states = solcast_states_dict.get(self._solcast_entity_id, [])

            # Process to daily yield.
            for state in solcast_states:
                try:
                    val = float(state.state)
                    # Group by the date it was forecasting for (tomorrow relative to last_changed)
                    forecast_date = (state.last_changed + timedelta(days=1)).date()
                    if forecast_date < end_date.date():
                        daily_yields[forecast_date] = val
                except (ValueError, TypeError):
                    continue

        if not daily_yields:
            _LOGGER.warning("No historical Solcast data found for analog search.")
            return []

        # DIAGNOSTIC: Dump the entire dataset to prove what is available
        import json
        try:
            dump_data = {str(k): v for k, v in daily_yields.items()}
            with open(self._hass.config.path("analog_search_dataset.json"), "w") as f:
                json.dump(dump_data, f, indent=2)
        except Exception as e:
            _LOGGER.error(f"Failed to dump debug dataset: {e}")

        # Find 5 most recent days that are within a 15% (or 2kWh) tolerance
        tolerance = max(2.0, target_kwh * 0.15)
        candidate_days = [
            (d_date, d_yield) for d_date, d_yield in daily_yields.items()
            if abs(d_yield - target_kwh) <= tolerance
        ]

        if candidate_days:
            # Sort the candidates by date descending (most recent first)
            candidate_days.sort(key=lambda x: x[0], reverse=True)
            top_5_days = candidate_days[:5]
        else:
            # Fallback to closest 5 regardless of recency if none within tolerance
            sorted_by_error = sorted(daily_yields.items(), key=lambda x: abs(x[1] - target_kwh))
            top_5_days = sorted_by_error[:5]

        analog_days = []
        for d_date, d_yield in top_5_days:
            day_start = dt_util.now().replace(
                year=d_date.year, month=d_date.month, day=d_date.day,
                hour=0, minute=0, second=0, microsecond=0
            )
            day_end = day_start + timedelta(days=1)

            entity_ids = []
            if self._import_price_entity_id:
                entity_ids.append(self._import_price_entity_id)
            if self._export_price_entity_id:
                entity_ids.append(self._export_price_entity_id)
            if self._load_entity_id:
                entity_ids.append(self._load_entity_id)

            if not entity_ids:
                continue

            day_states_dict = history.get_significant_states(
                self._hass,
                day_start,
                day_end,
                entity_ids=entity_ids,
            )

            # Process Import Price
            import_curve = [0.0] * 288
            if self._import_price_entity_id:
                states = day_states_dict.get(self._import_price_entity_id, [])
                if states:
                    import_curve = self._normalize_to_288(states, day_start)
                else:
                    import_curve = self._get_lts_curve(self._import_price_entity_id, day_start, day_end)

            # Process Export Price
            export_curve = [0.0] * 288
            if self._export_price_entity_id:
                states = day_states_dict.get(self._export_price_entity_id, [])
                if states:
                    export_curve = self._normalize_to_288(states, day_start)
                else:
                    export_curve = self._get_lts_curve(self._export_price_entity_id, day_start, day_end)

            # Process Load Profile
            load_curve = [0.0] * 288
            if self._load_entity_id:
                states = day_states_dict.get(self._load_entity_id, [])
                if states:
                    load_curve = self._normalize_to_288(states, day_start)
                else:
                    load_curve = self._get_lts_curve(self._load_entity_id, day_start, day_end)

            analog_days.append(
                AnalogDay(
                    date=day_start,
                    pv_yield=d_yield,
                    pricing_curve=import_curve,
                    export_curve=export_curve,
                    load_curve=load_curve,
                )
            )

        return analog_days

    def _average_curves(self, analog_days: list[AnalogDay], attr_name: str) -> list[float]:
        """Mathematically average the selected curve of the given analog days."""
        if not analog_days:
            return []

        curve_length = len(getattr(analog_days[0], attr_name))
        if curve_length == 0:
            return []

        averaged = [0.0] * curve_length
        for day in analog_days:
            curve = getattr(day, attr_name)
            for i in range(curve_length):
                averaged[i] += curve[i]

        for i in range(curve_length):
            averaged[i] /= len(analog_days)

        return averaged
