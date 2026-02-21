"""DataUpdateCoordinator for House Battery Control."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_RATE_MAX,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_POWER_INVERT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_EXPORT_PRICE_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_IMPORT_PRICE_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_INVERTER_LIMIT_MAX,
    CONF_LOAD_HIGH_TEMP_THRESHOLD,
    CONF_LOAD_LOW_TEMP_THRESHOLD,
    CONF_LOAD_SENSITIVITY_HIGH_TEMP,
    CONF_LOAD_SENSITIVITY_LOW_TEMP,
    CONF_LOAD_TODAY_ENTITY,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    CONF_SOLAR_ENTITY,
    CONF_SOLCAST_TODAY_ENTITY,
    CONF_SOLCAST_TOMORROW_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SOLCAST_TODAY,
    DEFAULT_SOLCAST_TOMORROW,
    DOMAIN,
)
from .execute import PowerwallExecutor
from .fsm.base import FSMContext
from .fsm.default import DefaultBatteryStateMachine
from .load import LoadPredictor
from .rates import RatesManager
from .solar.solcast import SolcastSolar
from .weather import WeatherManager

_LOGGER = logging.getLogger(__name__)

class HBCDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching House Battery Control data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.entry_id = entry_id
        self.config = config
        self._update_count = 0

        # Initialize Managers
        self.rates = RatesManager(
            hass,
            config.get(CONF_IMPORT_PRICE_ENTITY, ""),
            config.get(CONF_EXPORT_PRICE_ENTITY, ""),
        )
        self.weather = WeatherManager(hass, config.get(CONF_WEATHER_ENTITY, ""))
        self.load_predictor = LoadPredictor(hass)

        # Solar Provider (reads from Solcast HA integration entities)
        self.solar = SolcastSolar(
            hass,
            forecast_today_entity=config.get(CONF_SOLCAST_TODAY_ENTITY, DEFAULT_SOLCAST_TODAY),
            forecast_tomorrow_entity=config.get(CONF_SOLCAST_TOMORROW_ENTITY, DEFAULT_SOLCAST_TOMORROW),
        )

        # FSM + Executor
        self.fsm = DefaultBatteryStateMachine()
        self.executor = PowerwallExecutor(hass, config)

        # Set up state tracking for immediate FSM recalculation
        telemetry_entities = [
            self.config.get(CONF_BATTERY_SOC_ENTITY),
            self.config.get(CONF_BATTERY_POWER_ENTITY),
            self.config.get(CONF_SOLAR_ENTITY),
            self.config.get(CONF_GRID_ENTITY),
            self.config.get(CONF_LOAD_TODAY_ENTITY),
        ]

        self._tracked_entities = [entity for entity in telemetry_entities if entity]

        if self._tracked_entities:
            async_track_state_change_event(
                hass,
                self._tracked_entities,
                self._async_on_state_change
            )

    async def _async_on_state_change(self, event) -> None:
        """Trigger an immediate plan update when a vital telemetry entity changes state."""
        await self.async_request_refresh()

    def _get_sensor_value(self, entity_id: str) -> float:
        """Get float value from a sensor entity."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            _LOGGER.debug(f"Sensor {entity_id} is unavailable")
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.error(f"Could not convert {entity_id} state '{state.state}' to float")
            return 0.0

    def _build_sensor_diagnostics(self) -> list[dict[str, Any]]:
        """Build sensor availability report for API diagnostics (spec 2.4)."""
        sensor_keys = [
            CONF_BATTERY_SOC_ENTITY, CONF_BATTERY_POWER_ENTITY,
            CONF_SOLAR_ENTITY, CONF_GRID_ENTITY,
            CONF_IMPORT_PRICE_ENTITY, CONF_EXPORT_PRICE_ENTITY,
            CONF_WEATHER_ENTITY, CONF_LOAD_TODAY_ENTITY,
            CONF_IMPORT_TODAY_ENTITY, CONF_EXPORT_TODAY_ENTITY,
            CONF_SOLCAST_TODAY_ENTITY, CONF_SOLCAST_TOMORROW_ENTITY,
            CONF_SCRIPT_CHARGE, CONF_SCRIPT_CHARGE_STOP,
            CONF_SCRIPT_DISCHARGE, CONF_SCRIPT_DISCHARGE_STOP,
        ]
        diagnostics = []
        for key in sensor_keys:
            entity_id = self.config.get(key, "")
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            diagnostics.append({
                "entity_id": entity_id,
                "state": state.state if state else "not_found",
                "available": (
                    state is not None
                    and state.state != "unavailable"
                ),
                "attributes": dict(state.attributes) if state else {},
            })
        return diagnostics

    def _build_diagnostic_plan_table(
        self, rates: list[dict], solar_forecast: list[dict],
        load_forecast: list[dict], weather: list[dict],
        current_soc: float, current_state: str
    ) -> list[dict]:
        """Iterate over the rates timeline to simulate the internal FSM calculation engine's execution path.

        Outputs an interpolation table with explicitly rounded strings that matches the precise
        state logic Home Assistant will execute, mapped by UTC timestamp rather than array index.
        """
        from custom_components.house_battery_control.fsm.base import FSMContext
        from homeassistant.util import dt as dt_util

        # Pre-parse Load
        parsed_loads = []
        for lf in load_forecast:
            if not isinstance(lf, dict):
                continue
            start_str = lf.get("start", "")
            if not start_str:
                continue
            st = dt_util.parse_datetime(start_str) if isinstance(start_str, str) else start_str
            if st:
                parsed_loads.append({"start": st, "kw": float(lf.get("kw", 0.0))})

        # Pre-parse Weather
        parsed_weather = []
        for w in weather:
            if not isinstance(w, dict):
                continue
            w_time = w.get("datetime")
            w_time = dt_util.parse_datetime(w_time) if isinstance(w_time, str) else w_time
            if w_time:
                parsed_weather.append({"datetime": w_time, "temperature": w.get("temperature")})

        table = []
        cumulative = 0.0
        simulated_soc = current_soc

        for rate in rates:
            start = rate["start"]
            end = rate.get("end", start)

            # Rate metrics
            price = rate.get("import_price", rate.get("price", 0.0))
            export_price = rate.get("export_price", price * 0.8)

            duration_mins = max(1, int((end - start).total_seconds() / 60.0))
            duration_hours = duration_mins / 60.0

            # --- 1. PV Interpolation ---
            # Gather all 30-min Solar blocks that overlap this 5-min row
            matched_solar = []
            for s in solar_forecast:
                s_start_raw = s.get("period_start", s.get("start", ""))
                if not s_start_raw:
                    continue
                s_start = dt_util.parse_datetime(s_start_raw) if isinstance(s_start_raw, str) else s_start_raw

                from datetime import timedelta
                s_end_raw = s.get("period_end", s.get("end", ""))
                if s_end_raw:
                    s_end = dt_util.parse_datetime(s_end_raw) if isinstance(s_end_raw, str) else s_end_raw
                else:
                    s_end = s_start + timedelta(minutes=30) if s_start else None

                if s_start and s_end and (s_start < end and s_end > start):
                    matched_solar.append(float(s.get("pv_estimate", s.get("kw", 0.0))))

            pv_kw_avg = sum(matched_solar) / len(matched_solar) if matched_solar else 0.0
            pv_kwh = pv_kw_avg * duration_hours

            # --- 2. Load Interpolation ---
            matched_loads = [lf["kw"] for lf in parsed_loads if start <= lf["start"] < end]
            load_kw_avg = sum(matched_loads) / len(matched_loads) if matched_loads else 0.0

            # --- 3. Weather Interpolation (Nearest Neighbor) ---
            temp_c = None
            if parsed_weather:
                closest = min(parsed_weather, key=lambda w: abs((start - w["datetime"]).total_seconds()))
                temp_c = closest.get("temperature")

            # Build FSM Context for simulation
            ctx = FSMContext(
                soc=simulated_soc,
                solar_production=pv_kw_avg,
                load_power=load_kw_avg,
                grid_voltage=230.0,
                current_price=price,
                forecast_solar=solar_forecast,
                forecast_load=load_forecast,
                forecast_price=rates
            )

            if self.fsm:
                sim_res = self.fsm.calculate_next_state(ctx)
                state = sim_res.state
                inverter_limit = getattr(self, "inverter_limit_kw", 10.0)
                limit_pct = min(100.0, (abs(sim_res.limit_kw) / inverter_limit) * 100.0) if inverter_limit > 0 else 0.0

                # Flow Physics
                capacity = getattr(self, "capacity_kwh", 27.0)
                if state == "CHARGE_GRID":
                    sim_battery_p = sim_res.limit_kw
                elif state == "CHARGE_SOLAR":
                    sim_battery_p = sim_res.limit_kw
                elif state == "DISCHARGE_HOME":
                    sim_battery_p = -sim_res.limit_kw
                else:
                    sim_battery_p = 0.0

                # Battery impact
                soc_delta = (sim_battery_p * duration_hours) / capacity * 100.0
                next_soc = max(0.0, min(100.0, simulated_soc + soc_delta))

                # Grid impact (Cost)
                # Load minus PV minus Battery flow (where Battery consuming = positive flow)
                net_import_kw = load_kw_avg - pv_kw_avg + sim_battery_p
                interval_kwh = net_import_kw * duration_hours

                # Assign to export price if negative flow
                if interval_kwh < 0:
                    interval_cost = interval_kwh * export_price / 100.0
                else:
                    interval_cost = interval_kwh * price / 100.0

                cumulative += interval_cost
            else:
                state = "IDLE"
                limit_pct = 0.0
                interval_cost = 0.0
                next_soc = simulated_soc

            table.append({
                "Time": start.strftime("%H:%M") if hasattr(start, "strftime") else str(start),
                "Local Time": dt_util.as_local(start).strftime("%H:%M") if hasattr(start, "strftime") else str(start),
                "Import Rate": f"{price:.2f}",
                "Export Rate": f"{export_price:.2f}",
                "FSM State": state,
                "Inverter Limit": f"{limit_pct:.0f}%",
                "PV Forecast": f"{pv_kwh:.2f}",
                "Load Forecast": f"{load_kw_avg:.2f}",
                "Air Temp Forecast": f"{temp_c:.1f}°C" if temp_c is not None else "—",
                "SoC Forecast": f"{simulated_soc:.1f}%",
                "Interval Cost": f"${interval_cost:.4f}",
                "Cumulative Total": f"${cumulative:.2f}",
            })

            # Carry over SoC
            simulated_soc = next_soc

        return table

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Update Managed Inputs gracefully to prevent peripheral crashes from halting the core FSM tick
            try:
                self.rates.update()
            except Exception as e:
                _LOGGER.warning("Rates plugin not ready on boot: %s", e)

            try:
                await self.weather.async_update()
            except Exception as e:
                _LOGGER.warning("Weather plugin not ready on boot: %s", e)

            # Fetch Current Telemetry with Inversion Logic
            soc = self._get_sensor_value(self.config.get(CONF_BATTERY_SOC_ENTITY, ""))

            raw_battery_p = self._get_sensor_value(self.config.get(CONF_BATTERY_POWER_ENTITY, ""))
            battery_p = raw_battery_p * (-1.0 if self.config.get(CONF_BATTERY_POWER_INVERT) else 1.0)

            solar_p = self._get_sensor_value(self.config.get(CONF_SOLAR_ENTITY, ""))

            raw_grid_p = self._get_sensor_value(self.config.get(CONF_GRID_ENTITY, ""))
            grid_p = raw_grid_p * (-1.0 if self.config.get(CONF_GRID_POWER_INVERT) else 1.0)

            # Cumulative Today
            load_today = self._get_sensor_value(self.config.get(CONF_LOAD_TODAY_ENTITY, ""))
            import_today = self._get_sensor_value(self.config.get(CONF_IMPORT_TODAY_ENTITY, ""))
            export_today = self._get_sensor_value(self.config.get(CONF_EXPORT_TODAY_ENTITY, ""))

            # Derive House Load (Instantaneous)
            # Load = Solar + Grid - Battery
            # (Assumes Grid: + Import, Battery: + Charge)
            load_p = solar_p + grid_p - battery_p
            if load_p < 0:
                load_p = 0.0

            # Fetch Solar Forecast gracefully
            solar_forecast = []
            try:
                solar_forecast = await self.solar.async_get_forecast()
            except Exception as e:
                _LOGGER.warning("Solcast plugin not ready on boot: %s", e)

            # Predict Load
            start_time = self.rates.get_rates()[0]["start"] if self.rates.get_rates() else None
            if not start_time:
                start_time = dt_util.now()

            load_forecast = await self.load_predictor.async_predict(
                start_time=start_time,
                temp_forecast=self.weather.get_forecast(),
                high_sensitivity=self.config.get(CONF_LOAD_SENSITIVITY_HIGH_TEMP, 0.2),
                low_sensitivity=self.config.get(CONF_LOAD_SENSITIVITY_LOW_TEMP, 0.3),
                high_threshold=self.config.get(CONF_LOAD_HIGH_TEMP_THRESHOLD, 25.0),
                low_threshold=self.config.get(CONF_LOAD_LOW_TEMP_THRESHOLD, 15.0),
                load_entity_id=self.config.get(CONF_LOAD_TODAY_ENTITY, ""),  # Ideally an instant load sensor, using what's available
            )

            # Build FSM context and run decision logic
            current_price = self.rates.get_import_price_at(dt_util.now())

            fsm_context = FSMContext(
                soc=soc,
                solar_production=solar_p,
                load_power=load_p,
                grid_voltage=240.0,
                current_price=current_price,
                forecast_solar=solar_forecast,
                forecast_load=load_forecast,
                forecast_price=self.rates.get_rates(),
            )
            fsm_result = self.fsm.calculate_next_state(fsm_context)

            # Apply state to Powerwall
            await self.executor.apply_state(fsm_result.state, fsm_result.limit_kw)

            # Return data for sensors and dashboard
            self._update_count += 1
            return {
                "soc": round(soc, 1),
                "solar_power": round(solar_p, 2),
                "grid_power": round(grid_p, 2),
                "battery_power": round(battery_p, 2),
                "load_power": round(load_p, 2),
                "load_today": round(load_today, 2),
                "import_today": round(import_today, 2),
                "export_today": round(export_today, 2),
                "current_price": current_price,
                "rates": self.rates.get_rates(),
                "weather": self.weather.get_forecast(),
                "solar_forecast": solar_forecast,
                "load_forecast": load_forecast,
                # Constants
                "capacity": self.config.get(CONF_BATTERY_CAPACITY, 27.0),
                "charge_rate_max": self.config.get(CONF_BATTERY_CHARGE_RATE_MAX, 6.3),
                "inverter_limit": self.config.get(CONF_INVERTER_LIMIT_MAX, 10.0),
                # FSM results
                "state": fsm_result.state,
                "reason": fsm_result.reason,
                "limit_kw": fsm_result.limit_kw,
                "plan_html": self.executor.get_command_summary(),
                "plan": self._build_diagnostic_plan_table(
                    self.rates.get_rates(), solar_forecast, load_forecast,
                    self.weather.get_forecast(), soc, fsm_result.state
                ),
                "sensors": self._build_sensor_diagnostics(),
                "last_update": dt_util.utcnow().isoformat(),
                "update_count": self._update_count,
                "load_history": getattr(self.load_predictor, "last_history", []),
            }
        except Exception as err:
            raise UpdateFailed(f"Error in HBC update cycle: {err}")
