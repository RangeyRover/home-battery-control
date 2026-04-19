"""DataUpdateCoordinator for House Battery Control."""

from __future__ import annotations

import logging
from collections import deque
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_RATE_MAX,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_POWER_INVERT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENT_EXPORT_PRICE_ENTITY,
    CONF_CURRENT_IMPORT_PRICE_ENTITY,
    CONF_EXPORT_PRICE_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_IMPORT_PRICE_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_INVERTER_LIMIT_MAX,
    CONF_LOAD_CACHE_TTL,
    CONF_LOAD_HIGH_TEMP_THRESHOLD,
    CONF_LOAD_LOW_TEMP_THRESHOLD,
    CONF_LOAD_POWER_ENTITY,
    CONF_LOAD_SENSITIVITY_HIGH_TEMP,
    CONF_LOAD_SENSITIVITY_LOW_TEMP,
    CONF_LOAD_TODAY_ENTITY,
    CONF_NO_IMPORT_PERIODS,
    CONF_OBSERVATION_MODE,
    CONF_RESERVE_SOC,
    CONF_SOLAR_ENTITY,
    CONF_SOLCAST_TODAY_ENTITY,
    CONF_SOLCAST_TOMORROW_ENTITY,
    CONF_USE_AMBER_EXPRESS,
    CONF_WEATHER_ENTITY,
    DEFAULT_LOAD_CACHE_TTL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SOLCAST_TODAY,
    DEFAULT_SOLCAST_TOMORROW,
    DOMAIN,
)
from .execute import PowerwallExecutor
from .fsm.base import FSMContext, SolverInputs
from .fsm.lin_fsm import (
    LinearBatteryStateMachine,
    _is_in_no_import_period,
    _parse_no_import_periods,
)
from .load import LoadPredictor
from .rates import RatesManager
from .rates_predictor import SyntheticRatesPredictor
from .solar.solcast import SolcastSolar
from .telemetry_tracker import TelemetryCostTracker
from .weather import WeatherManager

_LOGGER = logging.getLogger(__name__)


class HBCDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching House Battery Control data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict[str, Any],
        telemetry_tracker: TelemetryCostTracker,
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
        self.telemetry_tracker = telemetry_tracker
        self._update_count = 0
        self.dp_target_soc = None

        self.acquisition_cost: float = 0.10
        self.store = Store(hass, 1, "house_battery_control.cost_data")
        self._costs_loaded = False
        self._last_saved_acquisition: float = 0.10
        self._last_update_time = None
        self._last_grid_power = 0.0
        self._last_buy_price = 0.0
        self._last_sell_price = 0.0

        # Feature 027: Debug replay snapshot
        self._solver_snapshot: dict | None = None
        self._state_transitions: deque = deque(maxlen=10)
        self._previous_state: str | None = None

        # Initialize Managers
        self.rates = RatesManager(
            hass,
            config.get(CONF_IMPORT_PRICE_ENTITY, ""),
            config.get(CONF_EXPORT_PRICE_ENTITY, ""),
            use_amber_express=config.get(CONF_USE_AMBER_EXPRESS, False),
        )
        self.weather = WeatherManager(hass, config.get(CONF_WEATHER_ENTITY, ""))
        self.load_predictor = LoadPredictor(hass)
        self.load_predictor.CACHE_TTL_MINUTES = int(
            config.get(CONF_LOAD_CACHE_TTL, DEFAULT_LOAD_CACHE_TTL)
        )

        # Solar Provider (reads from Solcast HA integration entities)
        self.solar = SolcastSolar(
            hass,
            forecast_today_entity=config.get(CONF_SOLCAST_TODAY_ENTITY, DEFAULT_SOLCAST_TODAY),
            forecast_tomorrow_entity=config.get(
                CONF_SOLCAST_TOMORROW_ENTITY, DEFAULT_SOLCAST_TOMORROW
            ),
        )

        self.synthetic_predictor = SyntheticRatesPredictor(
            hass,
            config.get(CONF_SOLCAST_TOMORROW_ENTITY, DEFAULT_SOLCAST_TOMORROW),
            config.get(CONF_IMPORT_PRICE_ENTITY, ""),
            config.get(CONF_EXPORT_PRICE_ENTITY, ""),
            config.get(CONF_LOAD_POWER_ENTITY, "")
        )

        # FSM + Executor
        self.fsm = LinearBatteryStateMachine()
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
                hass, self._tracked_entities, self._async_on_state_change
            )

    @property
    def cumulative_cost(self) -> float:
        """Get the isolated cumulative cost from the telemetry tracker."""
        return self.telemetry_tracker.cumulative_cost

    async def async_load_stored_costs(self) -> None:
        """Load persistent cost data from the .storage directory."""
        try:
            data = await self.store.async_load()
            if data:
                # The Store legacy payload might still have 'cumulative_cost', but we only care about acquisition now
                self.acquisition_cost = data.get("acquisition_cost", 0.10)
            else:
                self.acquisition_cost = 0.10
            self._last_saved_acquisition = self.acquisition_cost
        finally:
            self._costs_loaded = True

        # One-shot acquisition cost override from config options
        from .const import CONF_ACQ_COST_OVERRIDE, CONF_ACQ_COST_OVERRIDE_VALUE
        if self.config.get(CONF_ACQ_COST_OVERRIDE, False):
            override_val = self.config.get(CONF_ACQ_COST_OVERRIDE_VALUE, 0.135)
            _LOGGER.info(
                "Applying one-shot acquisition cost override: %s -> %s",
                self.acquisition_cost, override_val,
            )
            self.acquisition_cost = override_val
            # Persist immediately
            self.store.async_delay_save(
                lambda: {
                    "acquisition_cost": self.acquisition_cost,
                },
                60,
            )
            # Clear the flag so it doesn't fire again
            new_data = dict(self.config_entry.data)
            new_data[CONF_ACQ_COST_OVERRIDE] = False
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )

        _LOGGER.debug("Loaded HBC costs: Cumulative=$%s, Acquisition=%s c/kWh", self.cumulative_cost, self.acquisition_cost)

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
        from .diagnostics import build_sensor_diagnostics
        return build_sensor_diagnostics(self)

    def _build_diagnostic_plan_table(
        self,
        rates: list[Any],
        solar_forecast: list[Any],
        load_forecast: list[Any],
        weather: list[Any],
        current_soc: float,
        future_plan: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Iterate over the rates timeline to unpack the FSM LP solver's execution path.

        Outputs an interpolation table with explicitly rounded strings that matches the precise
        state logic Home Assistant will execute, mapped by UTC timestamp rather than array index.
        """
        from .diagnostics import build_diagnostic_plan_table
        return build_diagnostic_plan_table(
            self, rates, solar_forecast, load_forecast, weather, current_soc, future_plan
        )

    def _build_solver_inputs(
        self,
        rates_list: list[Any],
        forecast_load: list[Any],
        forecast_solar: list[Any],
        current_price: float,
        current_export_price: float,
    ) -> SolverInputs:
        n = 288

        # --- Price arrays ---
        price_buy: list[float] = []
        price_sell: list[float] = []
        for i in range(n):
            if i < len(rates_list):
                entry = rates_list[i]
                price_buy.append(float(entry.get("import_price", 0.0)))
                price_sell.append(float(entry.get("export_price", 0.0)))
            elif price_buy:
                price_buy.append(price_buy[-1])
                price_sell.append(price_sell[-1])
            else:
                price_buy.append(0.0)
                price_sell.append(0.0)

        # Override row-0 with live price (FR-002)
        if current_price is not None:
            price_buy[0] = float(current_price)
        elif rates_list:
            price_buy[0] = float(rates_list[0].get("import_price", 0.0))

        if current_export_price is not None:
            price_sell[0] = float(current_export_price)
        elif rates_list:
            price_sell[0] = float(rates_list[0].get("export_price", 0.0))

        # --- Load / PV arrays (kW → kWh per 5-min step) ---
        step_hours = 5.0 / 60.0

        load_kwh: list[float] = []
        for i in range(n):
            if i < len(forecast_load):
                entry = forecast_load[i]
                kw = float(entry.get("kw", 0.0)) if isinstance(entry, dict) else 0.0
                load_kwh.append(kw * step_hours)
            elif load_kwh:
                load_kwh.append(load_kwh[-1])
            else:
                load_kwh.append(0.0)

        pv_kwh: list[float] = []
        for i in range(n):
            if i < len(forecast_solar):
                entry = forecast_solar[i]
                kw = float(entry.get("kw", 0.0)) if isinstance(entry, dict) else 0.0
                pv_kwh.append(kw * step_hours)
            elif pv_kwh:
                pv_kwh.append(pv_kwh[-1])
            else:
                pv_kwh.append(0.0)

        # --- No-import period resolution (FR-004) ---
        no_import_steps: set[int] | None = None
        no_import_cfg = self.config.get(CONF_NO_IMPORT_PERIODS, "")
        if no_import_cfg:
            periods = _parse_no_import_periods(no_import_cfg)
            if periods:
                blocked: set[int] = set()
                for t in range(n):
                    if t < len(rates_list):
                        rate_start = rates_list[t].get("start")
                        if rate_start is not None:
                            from homeassistant.util import dt as dt_util
                            local_time = dt_util.as_local(rate_start).time()
                            if _is_in_no_import_period(local_time, periods):
                                blocked.add(t)
                    else:
                        # Beyond rates data — extrapolate time
                        if rates_list:
                            from datetime import timedelta
                            last_start = rates_list[-1].get("start")
                            if last_start is not None:
                                from homeassistant.util import dt as dt_util
                                extrapolated = last_start + timedelta(minutes=5 * (t - len(rates_list) + 1))
                                local_time = dt_util.as_local(extrapolated).time()
                                if _is_in_no_import_period(local_time, periods):
                                    blocked.add(t)
                no_import_steps = blocked if blocked else None

        return SolverInputs(
            price_buy=price_buy,
            price_sell=price_sell,
            load_kwh=load_kwh,
            pv_kwh=pv_kwh,
            no_import_steps=no_import_steps,
        )

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
            battery_p = raw_battery_p * (
                -1.0 if self.config.get(CONF_BATTERY_POWER_INVERT) else 1.0
            )

            solar_p = self._get_sensor_value(self.config.get(CONF_SOLAR_ENTITY, ""))

            raw_grid_p = self._get_sensor_value(self.config.get(CONF_GRID_ENTITY, ""))
            grid_p = raw_grid_p * (-1.0 if self.config.get(CONF_GRID_POWER_INVERT) else 1.0)

            # Cumulative Today
            load_today = self._get_sensor_value(self.config.get(CONF_LOAD_TODAY_ENTITY, ""))
            import_today = self._get_sensor_value(self.config.get(CONF_IMPORT_TODAY_ENTITY, ""))
            export_today = self._get_sensor_value(self.config.get(CONF_EXPORT_TODAY_ENTITY, ""))

            # Fetch Load Power gracefully
            # Preferred: Dedicated sensor if configured by user
            load_entity = self.config.get(CONF_LOAD_POWER_ENTITY, "")
            if load_entity:
                load_p = self._get_sensor_value(load_entity)
            else:
                # Fallback Derivation: Load = Solar + Grid + Battery
                # (Assumes standard HA polarity: Grid + Import, Battery + Discharge)
                load_p = solar_p + grid_p + battery_p

            if load_p < 0:
                load_p = 0.0

            # Fetch Solar Forecast gracefully
            solar_forecast = []
            try:
                solar_forecast = await self.solar.async_get_forecast()
            except Exception as e:
                _LOGGER.warning("Solcast plugin not ready on boot: %s", e)

            # Fetch synthetic outlook
            synthetic_analog_days = []
            synthetic_pricing_curve = []
            synthetic_export_curve = []
            synthetic_load_curve = []
            try:
                (
                    synthetic_analog_days,
                    synthetic_pricing_curve,
                    synthetic_export_curve,
                    synthetic_load_curve
                ) = await self.synthetic_predictor.async_get_synthetic_outlook()
            except Exception as e:
                _LOGGER.error("Failed to generate synthetic outlook: %s", e)

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
                load_entity_id=self.config.get(
                    CONF_LOAD_TODAY_ENTITY, ""
                ),  # Ideally an instant load sensor, using what's available
                weather_entity_id=self.config.get(CONF_WEATHER_ENTITY, ""),
            )

            # Align Solar Forecast to Rates Timeline
            from .context_builder import align_forecasts
            rates_timeline = self.rates.get_rates()
            aligned_solar, load_forecast = align_forecasts(rates_timeline, solar_forecast, load_forecast)

                # Build FSM context and run decision logic
            current_import_entity = self.config.get(CONF_CURRENT_IMPORT_PRICE_ENTITY)
            if current_import_entity:
                current_price = self._get_sensor_value(current_import_entity)
            else:
                current_price = self.rates.get_import_price_at(dt_util.now())

            current_export_entity = self.config.get(CONF_CURRENT_EXPORT_PRICE_ENTITY)
            if current_export_entity:
                current_export_price = self._get_sensor_value(current_export_entity)
            else:
                current_export_price = self.rates.get_export_price_at(dt_util.now())

            fsm_context = FSMContext(
                soc=soc,
                solar_production=solar_p,
                load_power=load_p,
                grid_voltage=240.0,
                current_price=current_price,
                forecast_solar=aligned_solar,
                forecast_load=load_forecast,
                forecast_price=self.rates.get_rates(),
                config={
                    "capacity_kwh": self.config.get(CONF_BATTERY_CAPACITY, 27.0),
                    "battery_rate_max": self.config.get(CONF_BATTERY_CHARGE_RATE_MAX, 6.3),
                    "inverter_limit": self.config.get(CONF_INVERTER_LIMIT_MAX, 10.0),
                    "reserve_soc": self.config.get(CONF_RESERVE_SOC, 0.0),
                    "no_import_periods": self.config.get(CONF_NO_IMPORT_PERIODS, ""),
                },
                acquisition_cost=self.acquisition_cost,
                cumulative_cost=self.cumulative_cost,
                current_export_price=current_export_price,
                solver_inputs=self._build_solver_inputs(
                    rates_list=self.rates.get_rates(),
                    forecast_load=load_forecast,
                    forecast_solar=aligned_solar,
                    current_price=current_price,
                    current_export_price=current_export_price,
                ),
            )
            # Run decision logic in background thread
            fsm_result = await self.hass.async_add_executor_job(
                self.fsm.calculate_next_state, fsm_context
            )

            # --- Feature 027: Capture solver snapshot for debug replay ---
            si = fsm_context.solver_inputs
            snapshot = {
                "timestamp": dt_util.utcnow().isoformat(),
                "solver_inputs": {
                    "price_buy": list(si.price_buy) if si else [],
                    "price_sell": list(si.price_sell) if si else [],
                    "load_kwh": list(si.load_kwh) if si else [],
                    "pv_kwh": list(si.pv_kwh) if si else [],
                    "no_import_steps": sorted(si.no_import_steps) if si and si.no_import_steps else [],
                },
                "battery": {
                    "soc": round(soc, 2),
                    "capacity": self.config.get(CONF_BATTERY_CAPACITY, 27.0),
                    "charge_rate_max": self.config.get(CONF_BATTERY_CHARGE_RATE_MAX, 6.3),
                    "inverter_limit": self.config.get(CONF_INVERTER_LIMIT_MAX, 10.0),
                    "round_trip_efficiency": fsm_context.config.get("round_trip_efficiency", 0.90),
                    "reserve_soc": self.config.get(CONF_RESERVE_SOC, 0.0),
                },
                "acquisition_cost": round(self.acquisition_cost, 6),
                "result": {
                    "state": fsm_result.state,
                    "limit_kw": fsm_result.limit_kw,
                    "target_soc": getattr(fsm_result, "target_soc", None),
                },
            }
            self._solver_snapshot = snapshot

            # Auto-capture on state transition (FR-003)
            if self._previous_state is not None and fsm_result.state != self._previous_state:
                self._state_transitions.appendleft(snapshot)
            self._previous_state = fsm_result.state

            # Apply state to Powerwall
            await self.executor.apply_state(fsm_result.state, fsm_result.limit_kw)

            # Store native DP target SOC state
            self.dp_target_soc = getattr(fsm_result, "target_soc", None)

            future_plan = fsm_result.future_plan or []

            # --- Update historical cost trackers based on real elapsed time ---
            now = dt_util.utcnow()

            # Capture current states for the next interval calculation
            self._last_update_time = now
            self._last_grid_power = grid_p

            rates_list = self.rates.get_rates()
            if rates_list:
                price = rates_list[0].get("import_price", rates_list[0].get("price", 0.0))
                export_price = rates_list[0].get("export_price", price * 0.8)
                self._last_buy_price = price
                self._last_sell_price = export_price
            else:
                self._last_buy_price = 0.0
                self._last_sell_price = 0.0

            # NOTE: acquisition_cost is NOT synced from solver plan.
            # The solver's running_cost starts from terminal_valuation
            # (which floors via max()), creating a feedback loop (BUG-025A).
            # acquisition_cost is a coordinator-level tracked value.

            # Save to persistent storage if values drifted significantly since last save
            acq_drift = abs(self.acquisition_cost - self._last_saved_acquisition)

            if self._costs_loaded and acq_drift >= 0.0001:
                self._last_saved_acquisition = self.acquisition_cost

                self.store.async_delay_save(
                    lambda: {
                        "acquisition_cost": self.acquisition_cost
                    },
                    delay=1.0
                )

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
                # Config flags for dashboard visibility
                "no_import_periods": self.config.get(CONF_NO_IMPORT_PERIODS, ""),
                "observation_mode": self.config.get(CONF_OBSERVATION_MODE, False),
                # FSM results
                "state": fsm_result.state,
                "reason": fsm_result.reason,
                "limit_kw": fsm_result.limit_kw,
                "target_soc": self.dp_target_soc,
                "plan_html": self.executor.get_command_summary(),
                "plan": await self.hass.async_add_executor_job(
                    self._build_diagnostic_plan_table,
                    self.rates.get_rates(),
                    solar_forecast,
                    load_forecast,
                    self.weather.get_forecast(),
                    soc,
                    future_plan,
                ),
                "cumulative_cost": round(self.cumulative_cost, 2),
                "acquisition_cost": round(self.acquisition_cost, 4),
                "sensors": self._build_sensor_diagnostics(),
                "last_update": dt_util.utcnow().isoformat(),
                "update_count": self._update_count,
                "load_history": getattr(self.load_predictor, "last_history", []),
                # Feature 022: cache observability
                "load_cache_date": str(self.load_predictor.cache_date) if self.load_predictor.cache_date else None,
                "load_cache_refreshed_at": self.load_predictor.cache_refreshed_at.isoformat() if self.load_predictor.cache_refreshed_at else None,
                "load_history_start": self.load_predictor.history_start.isoformat() if self.load_predictor.history_start else None,
                "load_history_end": self.load_predictor.history_end.isoformat() if self.load_predictor.history_end else None,
                "load_cache_ttl_minutes": self.load_predictor.CACHE_TTL_MINUTES,
                # Feature 027: Debug replay
                "solver_snapshot": self._solver_snapshot,
                "state_transitions": list(self._state_transitions),
                # Feature 037: Synthetic Outlook
                "synthetic_analog_days": synthetic_analog_days,
                "synthetic_pricing_curve": synthetic_pricing_curve,
                "synthetic_export_curve": synthetic_export_curve,
                "synthetic_load_curve": synthetic_load_curve,
            }
        except Exception as err:
            raise UpdateFailed(f"Error in HBC update cycle: {err}")
