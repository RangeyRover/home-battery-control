"""The House Battery Control integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HBCDataUpdateCoordinator
from .web import HBCApiPingView, HBCApiStatusView, HBCConfigYamlView, HBCDashboardView, HBCPlanView

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up House Battery Control from a config entry."""

    coordinator = HBCDataUpdateCoordinator(hass, entry.entry_id, entry.data)

    # Perform first refresh
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "coordinator": coordinator
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register API views (consumed by panel JS)
    hass.http.register_view(HBCApiStatusView())
    hass.http.register_view(HBCApiPingView())
    hass.http.register_view(HBCConfigYamlView())

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
