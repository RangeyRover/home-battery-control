"""Config flow for House Battery Control integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yaml  # type: ignore
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TimeSelector,
)

from .const import (
    CONF_ACQ_COST_OVERRIDE,
    CONF_ACQ_COST_OVERRIDE_VALUE,
    CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
    CONF_ALLOW_EXPORT_ENTITY,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_RATE_MAX,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_POWER_INVERT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_CURRENT_EXPORT_PRICE_ENTITY,
    CONF_CURRENT_IMPORT_PRICE_ENTITY,
    CONF_EXPORT_MARGIN,
    CONF_EXPORT_PRICE_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_FIXED_TOU_OFFPEAK_END,
    CONF_FIXED_TOU_OFFPEAK_PRICE,
    CONF_FIXED_TOU_OFFPEAK_START,
    CONF_FIXED_TOU_PEAK_END,
    CONF_FIXED_TOU_PEAK_PRICE,
    CONF_FIXED_TOU_PEAK_START,
    CONF_FIXED_TOU_SHOULDER_PRICE,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_GUARD_DAYTIME_DEADLINE,
    CONF_GUARD_LOW_SOLAR_THRESHOLD,
    CONF_GUARD_OVERNIGHT_DEADLINE,
    CONF_GUARD_PEAK_SOLAR,
    CONF_GUARD_RENEWABLES_THRESHOLD,
    CONF_GUARD_TRIGGER_MODE,
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
    CONF_PANEL_ADMIN_ONLY,
    CONF_PRICING_MODE,
    CONF_RESERVE_SOC,
    CONF_ROUND_TRIP_EFFICIENCY,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    CONF_SOLAR_ENTITY,
    CONF_SOLCAST_TODAY_ENTITY,
    CONF_SOLCAST_TOMORROW_ENTITY,
    CONF_TRACKER_EXPORT_PRICE,
    CONF_TRACKER_IMPORT_PRICE,
    CONF_USE_AMBER_EXPRESS,
    CONF_WEATHER_ENTITY,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BATTERY_RATE_MAX,
    DEFAULT_EXPORT_MARGIN,
    DEFAULT_GUARD_DAYTIME_DEADLINE,
    DEFAULT_GUARD_LOW_SOLAR_THRESHOLD,
    DEFAULT_GUARD_OVERNIGHT_DEADLINE,
    DEFAULT_GUARD_PEAK_SOLAR,
    DEFAULT_GUARD_RENEWABLES_THRESHOLD,
    DEFAULT_GUARD_TRIGGER_MODE,
    DEFAULT_INVERTER_LIMIT,
    DEFAULT_LOAD_CACHE_TTL,
    DEFAULT_PANEL_ADMIN_ONLY,
    DEFAULT_RESERVE_SOC,
    DEFAULT_ROUND_TRIP_EFFICIENCY,
    DEFAULT_SOLCAST_TODAY,
    DEFAULT_SOLCAST_TOMORROW,
    DEFAULT_USE_AMBER_EXPRESS,
    DOMAIN,
    PRICING_MODE_AMBER,
    PRICING_MODE_FIXED_TOU,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for House Battery Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return HBCOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 0: Choose configuration method."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["manual", "yaml"],
        )

    async def async_step_yaml(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure using YAML (S2)."""
        errors = {}
        if user_input is not None:
            try:
                yaml_data = yaml.safe_load(user_input["yaml_config"])
                if not isinstance(yaml_data, dict):
                    raise ValueError("YAML must be a dictionary")

                # Dump to log for future reference
                _LOGGER.info(
                    "HBC YAML Config imported directly:\n%s", yaml.dump(yaml_data, sort_keys=True)
                )
                return self.async_create_entry(title="House Battery Control", data=yaml_data)
            except Exception as e:
                _LOGGER.error("YAML config error: %s", e)
                errors["base"] = "invalid_yaml"

        return self.async_show_form(
            step_id="yaml",
            data_schema=vol.Schema(
                {vol.Required("yaml_config"): TextSelector(TextSelectorConfig(multiline=True))}
            ),
            errors=errors,
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1: Telemetry (Power)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_pricing_mode()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BATTERY_SOC_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_BATTERY_POWER_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_BATTERY_POWER_INVERT, default=False): BooleanSelector(),
                    vol.Required(CONF_SOLAR_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_GRID_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_GRID_POWER_INVERT, default=True): BooleanSelector(),
                    vol.Optional(CONF_LOAD_POWER_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )


    async def async_step_pricing_mode(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1b: Pricing Mode."""
        if user_input is not None:
            self._data.update(user_input)
            if user_input.get(CONF_PRICING_MODE) == PRICING_MODE_FIXED_TOU:
                return await self.async_step_fixed_tou()
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="pricing_mode",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICING_MODE, default=PRICING_MODE_AMBER): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=PRICING_MODE_AMBER, label="Amber Dynamic"),
                                SelectOptionDict(value=PRICING_MODE_FIXED_TOU, label="Fixed Time-of-Use"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_fixed_tou(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1c: Fixed TOU."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="fixed_tou",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FIXED_TOU_PEAK_START, default="16:00:00"): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_PEAK_END, default="20:00:00"): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_PEAK_PRICE, default=40.0): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX)),
                    vol.Required(CONF_FIXED_TOU_OFFPEAK_START, default="00:00:00"): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_OFFPEAK_END, default="06:00:00"): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_OFFPEAK_PRICE, default=10.0): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX)),
                    vol.Required(CONF_FIXED_TOU_SHOULDER_PRICE, default=20.0): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX)),
                }
            ),
        )

    async def async_step_energy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 2: Energy & Metrics (Cumulative)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_cost_tracking()

        schema = {
            vol.Required(CONF_LOAD_TODAY_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_IMPORT_TODAY_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_EXPORT_TODAY_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_LOAD_SENSITIVITY_HIGH_TEMP, default=0.2): NumberSelector(
                NumberSelectorConfig(min=0, max=5, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LOAD_SENSITIVITY_LOW_TEMP, default=0.3): NumberSelector(
                NumberSelectorConfig(min=0, max=5, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LOAD_HIGH_TEMP_THRESHOLD, default=25.0): NumberSelector(
                NumberSelectorConfig(min=15, max=45, step=0.5, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LOAD_LOW_TEMP_THRESHOLD, default=15.0): NumberSelector(
                NumberSelectorConfig(min=0, max=25, step=0.5, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(CONF_LOAD_CACHE_TTL, default=DEFAULT_LOAD_CACHE_TTL): NumberSelector(
                NumberSelectorConfig(min=5, max=1440, step=5, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
            ),
            vol.Required(
                CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_BATTERY_CHARGE_RATE_MAX, default=DEFAULT_BATTERY_RATE_MAX
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_INVERTER_LIMIT_MAX, default=DEFAULT_INVERTER_LIMIT
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_RESERVE_SOC, default=DEFAULT_RESERVE_SOC
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1.0, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_ROUND_TRIP_EFFICIENCY, default=DEFAULT_ROUND_TRIP_EFFICIENCY
            ): NumberSelector(
                NumberSelectorConfig(min=0.5, max=1.0, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_EXPORT_MARGIN, default=DEFAULT_EXPORT_MARGIN
            ): NumberSelector(
                NumberSelectorConfig(min=0.0, max=1.0, step=0.001, mode=NumberSelectorMode.BOX)
            ),
        }

        if self._data.get(CONF_PRICING_MODE, PRICING_MODE_AMBER) == PRICING_MODE_AMBER:
            schema.update({
                vol.Required(CONF_IMPORT_PRICE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_EXPORT_PRICE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_USE_AMBER_EXPRESS, default=DEFAULT_USE_AMBER_EXPRESS): BooleanSelector(),
                vol.Optional(CONF_CURRENT_IMPORT_PRICE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_CURRENT_EXPORT_PRICE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
            })

        schema.update({
            vol.Required(CONF_WEATHER_ENTITY): EntitySelector(
                EntitySelectorConfig(domain="weather")
            ),
            vol.Required(
                CONF_SOLCAST_TODAY_ENTITY, default=DEFAULT_SOLCAST_TODAY
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_SOLCAST_TOMORROW_ENTITY, default=DEFAULT_SOLCAST_TOMORROW
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
        })

        return self.async_show_form(
            step_id="energy",
            data_schema=vol.Schema(schema),
        )

    async def async_step_cost_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: Cost Tracking (Optional)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_control()

        return self.async_show_form(
            step_id="cost_tracking",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_TRACKER_IMPORT_PRICE): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_TRACKER_EXPORT_PRICE): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    async def async_step_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4: Control Services (Optional — skip for debug mode)."""
        if user_input is not None:
            # If skip is checked, create entry without control entities
            if user_input.get("skip_control", False):
                _LOGGER.info("HBC Config final YAML:\n%s", yaml.dump(self._data, sort_keys=True))
                return self.async_create_entry(title="House Battery Control", data=self._data)
            self._data.update(user_input)
            # Remove the skip flag from stored data
            self._data.pop("skip_control", None)

            _LOGGER.info("HBC Config final YAML:\n%s", yaml.dump(self._data, sort_keys=True))
            return self.async_create_entry(title="House Battery Control", data=self._data)

        return self.async_show_form(
            step_id="control",
            data_schema=vol.Schema(
                {
                    vol.Required("skip_control", default=True): BooleanSelector(),
                    vol.Optional(CONF_ALLOW_CHARGE_FROM_GRID_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain=["switch", "script"])
                    ),
                    vol.Optional(CONF_ALLOW_EXPORT_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain=["select", "script"])
                    ),
                    vol.Optional(CONF_SCRIPT_CHARGE): EntitySelector(
                        EntitySelectorConfig(domain="script")
                    ),
                    vol.Optional(CONF_SCRIPT_CHARGE_STOP): EntitySelector(
                        EntitySelectorConfig(domain="script")
                    ),
                    vol.Optional(CONF_SCRIPT_DISCHARGE): EntitySelector(
                        EntitySelectorConfig(domain="script")
                    ),
                    vol.Optional(CONF_SCRIPT_DISCHARGE_STOP): EntitySelector(
                        EntitySelectorConfig(domain="script")
                    ),
                    vol.Optional(
                        CONF_NO_IMPORT_PERIODS,
                        default="",
                    ): TextSelector(TextSelectorConfig(type="text")),
                    vol.Optional(
                        CONF_GUARD_RENEWABLES_THRESHOLD,
                        default=self._data.get(CONF_GUARD_RENEWABLES_THRESHOLD, DEFAULT_GUARD_RENEWABLES_THRESHOLD),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="%")
                    ),
                    vol.Optional(
                        CONF_GUARD_LOW_SOLAR_THRESHOLD,
                        default=self._data.get(CONF_GUARD_LOW_SOLAR_THRESHOLD, DEFAULT_GUARD_LOW_SOLAR_THRESHOLD),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="%")
                    ),
                    vol.Optional(
                        CONF_GUARD_PEAK_SOLAR,
                        default=self._data.get(CONF_GUARD_PEAK_SOLAR, DEFAULT_GUARD_PEAK_SOLAR),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="kWh")
                    ),
                    vol.Optional(
                        CONF_GUARD_TRIGGER_MODE,
                        default=self._data.get(CONF_GUARD_TRIGGER_MODE, DEFAULT_GUARD_TRIGGER_MODE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="OR", label="OR"),
                                SelectOptionDict(value="AND", label="AND"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_GUARD_OVERNIGHT_DEADLINE,
                        default=self._data.get(CONF_GUARD_OVERNIGHT_DEADLINE, DEFAULT_GUARD_OVERNIGHT_DEADLINE),
                    ): TimeSelector(),
                    vol.Optional(
                        CONF_GUARD_DAYTIME_DEADLINE,
                        default=self._data.get(CONF_GUARD_DAYTIME_DEADLINE, DEFAULT_GUARD_DAYTIME_DEADLINE),
                    ): TimeSelector(),
                }
            ),
        )


class HBCOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for House Battery Control."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._data = dict(config_entry.data)
        # In HA, options override data over time. We'll simply merge them into the config data in the options property if available.
        # But this integration relies heavily on replacing full config, so we will re-save the config entry data.
        if config_entry.options:
            self._data.update(config_entry.options)

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["pricing_mode", "fixed_tou", "manual", "energy", "cost_tracking", "control"],
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Update Telemetry (Power) options."""
        if user_input is not None:
            self._data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=self._data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BATTERY_SOC_ENTITY, default=self._data.get(CONF_BATTERY_SOC_ENTITY)
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    vol.Required(
                        CONF_BATTERY_POWER_ENTITY, default=self._data.get(CONF_BATTERY_POWER_ENTITY)
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    vol.Required(
                        CONF_BATTERY_POWER_INVERT,
                        default=self._data.get(CONF_BATTERY_POWER_INVERT, False),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_SOLAR_ENTITY, default=self._data.get(CONF_SOLAR_ENTITY)
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    vol.Required(
                        CONF_GRID_ENTITY, default=self._data.get(CONF_GRID_ENTITY)
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    vol.Required(
                        CONF_GRID_POWER_INVERT, default=self._data.get(CONF_GRID_POWER_INVERT, True)
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_LOAD_POWER_ENTITY,
                        description={"suggested_value": self._data.get(CONF_LOAD_POWER_ENTITY)},
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                }
            ),
        )


    async def async_step_pricing_mode(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1b: Pricing Mode."""
        if user_input is not None:
            self._data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=self._data)
            if user_input.get(CONF_PRICING_MODE) == PRICING_MODE_FIXED_TOU:
                return await self.async_step_fixed_tou()
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="pricing_mode",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICING_MODE, default=self._data.get(CONF_PRICING_MODE, PRICING_MODE_AMBER)): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=PRICING_MODE_AMBER, label="Amber Dynamic"),
                                SelectOptionDict(value=PRICING_MODE_FIXED_TOU, label="Fixed Time-of-Use"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_fixed_tou(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Step 1c: Fixed TOU."""
        if user_input is not None:
            self._data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=self._data)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="fixed_tou",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_FIXED_TOU_PEAK_START, default=self._data.get(CONF_FIXED_TOU_PEAK_START, "16:00:00")): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_PEAK_END, default=self._data.get(CONF_FIXED_TOU_PEAK_END, "20:00:00")): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_PEAK_PRICE, default=self._data.get(CONF_FIXED_TOU_PEAK_PRICE, 40.0)): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX)),
                    vol.Required(CONF_FIXED_TOU_OFFPEAK_START, default=self._data.get(CONF_FIXED_TOU_OFFPEAK_START, "00:00:00")): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_OFFPEAK_END, default=self._data.get(CONF_FIXED_TOU_OFFPEAK_END, "06:00:00")): TimeSelector(),
                    vol.Required(CONF_FIXED_TOU_OFFPEAK_PRICE, default=self._data.get(CONF_FIXED_TOU_OFFPEAK_PRICE, 10.0)): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX)),
                    vol.Required(CONF_FIXED_TOU_SHOULDER_PRICE, default=self._data.get(CONF_FIXED_TOU_SHOULDER_PRICE, 20.0)): NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX)),
                }
            ),
        )

    async def async_step_energy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Update Energy & Metrics (Cumulative)."""
        if user_input is not None:
            # Apply one-shot acquisition cost override immediately (no restart)
            if user_input.get(CONF_ACQ_COST_OVERRIDE, False):
                override_val = user_input.get(CONF_ACQ_COST_OVERRIDE_VALUE, 0.135)
                domain_data = self.hass.data.get(DOMAIN, {})
                for entry_data in domain_data.values():
                    coord = entry_data.get("coordinator") if isinstance(entry_data, dict) else None
                    if coord and hasattr(coord, "acquisition_cost"):
                        _LOGGER.info(
                            "Applying acquisition cost override: %s -> %s",
                            coord.acquisition_cost, override_val,
                        )
                        coord.acquisition_cost = override_val
                        # Save immediately — integration reloads on options change,
                        # so async_delay_save would never fire before destruction
                        await coord.store.async_save({
                            "cumulative_cost": coord.cumulative_cost,
                            "acquisition_cost": coord.acquisition_cost,
                        })
                        break
                # Clear the flag so it doesn't fire again on restart
                user_input[CONF_ACQ_COST_OVERRIDE] = False

            self._data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=self._data)
            return self.async_create_entry(title="", data={})

        schema = {
            vol.Required(
                CONF_LOAD_TODAY_ENTITY, default=self._data.get(CONF_LOAD_TODAY_ENTITY)
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_IMPORT_TODAY_ENTITY, default=self._data.get(CONF_IMPORT_TODAY_ENTITY)
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_EXPORT_TODAY_ENTITY, default=self._data.get(CONF_EXPORT_TODAY_ENTITY)
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_LOAD_SENSITIVITY_HIGH_TEMP,
                default=self._data.get(CONF_LOAD_SENSITIVITY_HIGH_TEMP, 0.2),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=5, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_LOAD_SENSITIVITY_LOW_TEMP,
                default=self._data.get(CONF_LOAD_SENSITIVITY_LOW_TEMP, 0.3),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=5, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_LOAD_HIGH_TEMP_THRESHOLD,
                default=self._data.get(CONF_LOAD_HIGH_TEMP_THRESHOLD, 25.0),
            ): NumberSelector(
                NumberSelectorConfig(min=15, max=45, step=0.5, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_LOAD_LOW_TEMP_THRESHOLD,
                default=self._data.get(CONF_LOAD_LOW_TEMP_THRESHOLD, 15.0),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=25, step=0.5, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_LOAD_CACHE_TTL,
                default=self._data.get(CONF_LOAD_CACHE_TTL, DEFAULT_LOAD_CACHE_TTL),
            ): NumberSelector(
                NumberSelectorConfig(min=5, max=1440, step=5, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
            ),
            vol.Required(
                CONF_BATTERY_CAPACITY,
                default=self._data.get(CONF_BATTERY_CAPACITY, DEFAULT_BATTERY_CAPACITY),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_BATTERY_CHARGE_RATE_MAX,
                default=self._data.get(
                    CONF_BATTERY_CHARGE_RATE_MAX, DEFAULT_BATTERY_RATE_MAX
                ),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_INVERTER_LIMIT_MAX,
                default=self._data.get(CONF_INVERTER_LIMIT_MAX, DEFAULT_INVERTER_LIMIT),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_RESERVE_SOC,
                default=self._data.get(CONF_RESERVE_SOC, DEFAULT_RESERVE_SOC),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=100, step=1.0, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_ROUND_TRIP_EFFICIENCY,
                default=self._data.get(CONF_ROUND_TRIP_EFFICIENCY, DEFAULT_ROUND_TRIP_EFFICIENCY),
            ): NumberSelector(
                NumberSelectorConfig(min=0.5, max=1.0, step=0.01, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_EXPORT_MARGIN,
                default=self._data.get(CONF_EXPORT_MARGIN, DEFAULT_EXPORT_MARGIN),
            ): NumberSelector(
                NumberSelectorConfig(min=0.0, max=1.0, step=0.001, mode=NumberSelectorMode.BOX)
            ),
        }

        if self._data.get(CONF_PRICING_MODE, PRICING_MODE_AMBER) == PRICING_MODE_AMBER:
            schema.update({
                vol.Required(
                    CONF_IMPORT_PRICE_ENTITY, default=self._data.get(CONF_IMPORT_PRICE_ENTITY)
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Required(
                    CONF_EXPORT_PRICE_ENTITY, default=self._data.get(CONF_EXPORT_PRICE_ENTITY)
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(
                    CONF_USE_AMBER_EXPRESS, default=self._data.get(CONF_USE_AMBER_EXPRESS, DEFAULT_USE_AMBER_EXPRESS)
                ): BooleanSelector(),
                vol.Optional(
                    CONF_CURRENT_IMPORT_PRICE_ENTITY,
                    description={"suggested_value": self._data.get(CONF_CURRENT_IMPORT_PRICE_ENTITY)},
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Optional(
                    CONF_CURRENT_EXPORT_PRICE_ENTITY,
                    description={"suggested_value": self._data.get(CONF_CURRENT_EXPORT_PRICE_ENTITY)},
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            })

        schema.update({
            vol.Required(
                CONF_WEATHER_ENTITY, default=self._data.get(CONF_WEATHER_ENTITY)
            ): EntitySelector(EntitySelectorConfig(domain="weather")),
            vol.Required(
                CONF_SOLCAST_TODAY_ENTITY,
                default=self._data.get(CONF_SOLCAST_TODAY_ENTITY, DEFAULT_SOLCAST_TODAY),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Required(
                CONF_SOLCAST_TOMORROW_ENTITY,
                default=self._data.get(
                    CONF_SOLCAST_TOMORROW_ENTITY, DEFAULT_SOLCAST_TOMORROW
                ),
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_ACQ_COST_OVERRIDE,
                default=self._data.get(CONF_ACQ_COST_OVERRIDE, False),
            ): BooleanSelector(),
            vol.Optional(
                CONF_ACQ_COST_OVERRIDE_VALUE,
                default=self._data.get(CONF_ACQ_COST_OVERRIDE_VALUE, 0.135),
            ): NumberSelector(
                NumberSelectorConfig(min=0, max=1, step=0.001, mode=NumberSelectorMode.BOX)
            ),
        })

        return self.async_show_form(
            step_id="energy",
            data_schema=vol.Schema(schema),
        )

    async def async_step_cost_tracking(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update Cost Tracking (Optional)."""
        if user_input is not None:
            self._data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=self._data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="cost_tracking",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_TRACKER_IMPORT_PRICE,
                        description={"suggested_value": self._data.get(CONF_TRACKER_IMPORT_PRICE)},
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                    vol.Optional(
                        CONF_TRACKER_EXPORT_PRICE,
                        description={"suggested_value": self._data.get(CONF_TRACKER_EXPORT_PRICE)},
                    ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                }
            ),
        )

    async def async_step_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update Control Services options."""
        if user_input is not None:
            # Persist observation mode
            self._data[CONF_OBSERVATION_MODE] = user_input.pop(
                CONF_OBSERVATION_MODE, False
            )
            # Persist panel admin only
            self._data[CONF_PANEL_ADMIN_ONLY] = user_input.pop(
                CONF_PANEL_ADMIN_ONLY, DEFAULT_PANEL_ADMIN_ONLY
            )
            # Persist no-import periods (Feature 010)
            self._data[CONF_NO_IMPORT_PERIODS] = user_input.pop(
                CONF_NO_IMPORT_PERIODS, ""
            )
            # Handle script entities: strip empty values, store the rest
            for key in (
                CONF_SCRIPT_CHARGE,
                CONF_SCRIPT_CHARGE_STOP,
                CONF_SCRIPT_DISCHARGE,
                CONF_SCRIPT_DISCHARGE_STOP,
            ):
                val = user_input.get(key)
                if val in (None, ""):
                    self._data.pop(key, None)
                else:
                    self._data[key] = val

            # Persist low renewables guard settings (Feature 055)
            for key in (
                CONF_GUARD_RENEWABLES_THRESHOLD,
                CONF_GUARD_LOW_SOLAR_THRESHOLD,
                CONF_GUARD_PEAK_SOLAR,
                CONF_GUARD_TRIGGER_MODE,
                CONF_GUARD_OVERNIGHT_DEADLINE,
                CONF_GUARD_DAYTIME_DEADLINE,
            ):
                if key in user_input:
                    self._data[key] = user_input[key]

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=self._data
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="control",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_OBSERVATION_MODE,
                        default=self._data.get(CONF_OBSERVATION_MODE, False),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_SCRIPT_CHARGE,
                        description={
                            "suggested_value": self._data.get(CONF_SCRIPT_CHARGE)
                        },
                    ): EntitySelector(EntitySelectorConfig(domain="script")),
                    vol.Optional(
                        CONF_SCRIPT_CHARGE_STOP,
                        description={
                            "suggested_value": self._data.get(CONF_SCRIPT_CHARGE_STOP)
                        },
                    ): EntitySelector(EntitySelectorConfig(domain="script")),
                    vol.Optional(
                        CONF_SCRIPT_DISCHARGE,
                        description={
                            "suggested_value": self._data.get(CONF_SCRIPT_DISCHARGE)
                        },
                    ): EntitySelector(EntitySelectorConfig(domain="script")),
                    vol.Optional(
                        CONF_SCRIPT_DISCHARGE_STOP,
                        description={
                            "suggested_value": self._data.get(
                                CONF_SCRIPT_DISCHARGE_STOP
                            )
                        },
                    ): EntitySelector(EntitySelectorConfig(domain="script")),
                    vol.Optional(
                        CONF_PANEL_ADMIN_ONLY,
                        default=self._data.get(
                            CONF_PANEL_ADMIN_ONLY, DEFAULT_PANEL_ADMIN_ONLY
                        ),
                    ): BooleanSelector(),
                    vol.Optional(
                        CONF_NO_IMPORT_PERIODS,
                        description={
                            "suggested_value": self._data.get(CONF_NO_IMPORT_PERIODS, "")
                        },
                    ): TextSelector(TextSelectorConfig(type="text")),
                    vol.Optional(
                        CONF_GUARD_RENEWABLES_THRESHOLD,
                        default=self._data.get(CONF_GUARD_RENEWABLES_THRESHOLD, DEFAULT_GUARD_RENEWABLES_THRESHOLD),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="%")
                    ),
                    vol.Optional(
                        CONF_GUARD_LOW_SOLAR_THRESHOLD,
                        default=self._data.get(CONF_GUARD_LOW_SOLAR_THRESHOLD, DEFAULT_GUARD_LOW_SOLAR_THRESHOLD),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="%")
                    ),
                    vol.Optional(
                        CONF_GUARD_PEAK_SOLAR,
                        default=self._data.get(CONF_GUARD_PEAK_SOLAR, DEFAULT_GUARD_PEAK_SOLAR),
                    ): NumberSelector(
                        NumberSelectorConfig(min=0.0, max=100.0, step=0.1, mode=NumberSelectorMode.BOX, unit_of_measurement="kWh")
                    ),
                    vol.Optional(
                        CONF_GUARD_TRIGGER_MODE,
                        default=self._data.get(CONF_GUARD_TRIGGER_MODE, DEFAULT_GUARD_TRIGGER_MODE),
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value="OR", label="OR"),
                                SelectOptionDict(value="AND", label="AND"),
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_GUARD_OVERNIGHT_DEADLINE,
                        default=self._data.get(CONF_GUARD_OVERNIGHT_DEADLINE, DEFAULT_GUARD_OVERNIGHT_DEADLINE),
                    ): TimeSelector(),
                    vol.Optional(
                        CONF_GUARD_DAYTIME_DEADLINE,
                        default=self._data.get(CONF_GUARD_DAYTIME_DEADLINE, DEFAULT_GUARD_DAYTIME_DEADLINE),
                    ): TimeSelector(),
                }
            ),
        )
