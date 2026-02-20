"""DataUpdateCoordinator for House Battery Control."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
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

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            # Update Managed Inputs
            self.rates.update()
            await self.weather.async_update()

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

            # Fetch Solar Forecast
            solar_forecast = await self.solar.async_get_forecast()

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
                "soc": soc,
                "solar_power": solar_p,
                "grid_power": grid_p,
                "battery_power": battery_p,
                "load_power": load_p,
                "load_today": load_today,
                "import_today": import_today,
                "export_today": export_today,
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
                # Diagnostics (spec 2.4)
                "sensors": self._build_sensor_diagnostics(),
                "last_update": dt_util.utcnow().isoformat(),
                "update_count": self._update_count,
            }
        except Exception as err:
            raise UpdateFailed(f"Error in HBC update cycle: {err}")
