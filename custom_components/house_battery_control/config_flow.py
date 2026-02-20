"""Config flow for House Battery Control integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
    CONF_ALLOW_EXPORT_ENTITY,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_RATE_MAX,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_POWER_INVERT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_INVERTER_LIMIT_MAX,
    CONF_LOAD_HIGH_TEMP_THRESHOLD,
    CONF_LOAD_LOW_TEMP_THRESHOLD,
    CONF_LOAD_SENSITIVITY_HIGH_TEMP,
    CONF_LOAD_SENSITIVITY_LOW_TEMP,
    CONF_LOAD_TODAY_ENTITY,
    CONF_SOLAR_ENTITY,
    CONF_TARIFF_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_BATTERY_CAPACITY,
    DEFAULT_BATTERY_RATE_MAX,
    DEFAULT_INVERTER_LIMIT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for House Battery Control."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: Telemetry (Power)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_energy()

        return self.async_show_form(
            step_id="user",
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
                }
            ),
        )

    async def async_step_energy(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Energy & Metrics (Cumulative)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_control()

        return self.async_show_form(
            step_id="energy",
            data_schema=vol.Schema(
                {
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
                    vol.Required(CONF_BATTERY_CAPACITY, default=DEFAULT_BATTERY_CAPACITY): NumberSelector(
                        NumberSelectorConfig(min=0, max=100, step=0.1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_BATTERY_CHARGE_RATE_MAX, default=DEFAULT_BATTERY_RATE_MAX): NumberSelector(
                        NumberSelectorConfig(min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_INVERTER_LIMIT_MAX, default=DEFAULT_INVERTER_LIMIT): NumberSelector(
                        NumberSelectorConfig(min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required(CONF_TARIFF_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(CONF_WEATHER_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain="weather")
                    ),
                }
            ),
        )

    async def async_step_control(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Control Services."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="House Battery Control", data=self._data)

        return self.async_show_form(
            step_id="control",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ALLOW_CHARGE_FROM_GRID_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain=["switch", "script"])
                    ),
                    vol.Required(CONF_ALLOW_EXPORT_ENTITY): EntitySelector(
                        EntitySelectorConfig(domain=["select", "script"])
                    ),
                }
            ),
        )
