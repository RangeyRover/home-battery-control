"""The House Battery Control integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HBCDataUpdateCoordinator
from .web import HBCApiPingView, HBCApiStatusView, HBCLoadHistoryView, HBCConfigYamlView, HBCDashboardView, HBCPlanView

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up House Battery Control from a config entry."""

    config_data = dict(entry.data)
    if entry.options:
        config_data.update(entry.options)

    coordinator = HBCDataUpdateCoordinator(hass, entry.entry_id, config_data)

    # Perform first refresh
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": config_data,
        "coordinator": coordinator
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Defer a refresh until HA is fully started to ensure all peripheral integrations (Solcast, Weather) are ready
    async def _force_refresh_on_startup(_event):
        _LOGGER.info("Home Assistant started, triggering deferred HBC refresh")
        await coordinator.async_request_refresh()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _force_refresh_on_startup)

    # Register API views (consumed by panel JS)
    hass.http.register_view(HBCApiStatusView())
    hass.http.register_view(HBCApiPingView())
    hass.http.register_view(HBCConfigYamlView())
    hass.http.register_view(HBCLoadHistoryView())

    # Legacy HTML views (kept for backward compat)
    hass.http.register_view(HBCDashboardView())
    hass.http.register_view(HBCPlanView())

    # Register custom panel (spec 2.2)
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/hbc/frontend", str(FRONTEND_DIR), False)]
    )

    try:
        from homeassistant.components.frontend import (
            async_register_built_in_panel,
        )
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="HBC",
            sidebar_icon="mdi:battery-charging",
            frontend_url_path="hbc-panel",
            config={
                "_panel_custom": {
                    "name": "hbc-panel",
                    "module_url": "/hbc/frontend/hbc-panel.js",
                }
            },
        )
    except Exception as exc:
        _LOGGER.warning("Could not register HBC panel: %s", exc, exc_info=True)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
