"""The House Battery Control integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HBCDataUpdateCoordinator
from .web import HBCApiPingView, HBCApiStatusView, HBCDashboardView, HBCPlanView

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

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

    # Register web dashboard views
    hass.http.register_view(HBCDashboardView())
    hass.http.register_view(HBCPlanView())
    hass.http.register_view(HBCApiStatusView())
    hass.http.register_view(HBCApiPingView())

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
