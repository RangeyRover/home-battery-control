import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components.recorder import get_instance
from homeassistant.core import HomeAssistant
from sqlalchemy import text

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

    def _get_lts_curve(self, conn, entity_id: str, day_start: datetime, day_end: datetime) -> list[float]:
        """Retrieve the 5-minute curve from LTS statistics."""
        curve = [0.0] * 288

        try:
            # 1. Get metadata ID
            res_meta = conn.execute(
                text("SELECT id FROM statistics_meta WHERE statistic_id = :entity_id"),
                {"entity_id": entity_id}
            ).fetchone()

            if res_meta:
                meta_id = res_meta[0]
                start_ts = day_start.timestamp()
                end_ts = day_end.timestamp()

                res_stats = conn.execute(
                    text('''
                        SELECT start_ts, mean, state
                        FROM statistics
                        WHERE metadata_id = :meta_id AND start_ts >= :start_ts AND start_ts < :end_ts
                        ORDER BY start_ts ASC
                    '''),
                    {"meta_id": meta_id, "start_ts": start_ts, "end_ts": end_ts}
                ).fetchall()

                for row in res_stats:
                    ts, mean_val, state_val = row
                    val = mean_val if mean_val is not None else state_val
                    if val is None:
                        continue

                    dt = datetime.fromtimestamp(ts, tz=dt_util.UTC)
                    minutes_since_midnight = dt.hour * 60 + dt.minute
                    idx = int(minutes_since_midnight / 5)
                    if 0 <= idx < 288:
                        curve[idx] = float(val)
        except Exception as e:
            _LOGGER.error(f"LTS curve query failed for {entity_id}: {e}")

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

        try:
            engine = get_instance(self._hass).engine
            with engine.connect() as conn:
                daily_yields = {}

                # 1. Get metadata ID for Solcast
                res_meta = conn.execute(
                    text("SELECT id FROM statistics_meta WHERE statistic_id = :entity_id"),
                    {"entity_id": self._solcast_entity_id}
                ).fetchone()

                if res_meta:
                    meta_id = res_meta[0]
                    res_stats = conn.execute(
                        text('''
                            SELECT start_ts, max, mean, state
                            FROM statistics
                            WHERE metadata_id = :meta_id
                            ORDER BY start_ts ASC
                        '''),
                        {"meta_id": meta_id}
                    ).fetchall()

                    for row in res_stats:
                        start_ts, max_val, mean_val, state_val = row
                        val = max_val if max_val is not None else (mean_val if mean_val is not None else state_val)
                        if val is None:
                            continue

                        dt = datetime.fromtimestamp(start_ts, tz=dt_util.UTC)
                        forecast_date = (dt + timedelta(days=1)).date()

                        current_max = daily_yields.get(forecast_date, 0)
                        daily_yields[forecast_date] = max(val, current_max)

                if not daily_yields:
                    _LOGGER.warning("No historical Solcast data found for analog search.")
                    return []

                # Find 5 most recent days that are within a 5% tolerance
                tolerance = max(2.0, target_kwh * 0.05)
                candidate_days = [
                    (d_date, d_yield) for d_date, d_yield in daily_yields.items()
                    if abs(d_yield - target_kwh) <= tolerance
                ]

                if len(candidate_days) >= 5:
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

                    # Process Import Price
                    import_curve = [0.0] * 288
                    if self._import_price_entity_id:
                        import_curve = self._get_lts_curve(conn, self._import_price_entity_id, day_start, day_end)

                    # Process Export Price
                    export_curve = [0.0] * 288
                    if self._export_price_entity_id:
                        export_curve = self._get_lts_curve(conn, self._export_price_entity_id, day_start, day_end)

                    # Process Load Profile
                    load_curve = [0.0] * 288
                    if self._load_entity_id:
                        load_curve = self._get_lts_curve(conn, self._load_entity_id, day_start, day_end)

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

        except Exception as e:
            _LOGGER.error(f"Analog search crashed: {e}")
            return []


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
