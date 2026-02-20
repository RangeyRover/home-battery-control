"""Sensor platform for House Battery Control."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_PLAN_HTML, DOMAIN
from .coordinator import HBCDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: HBCDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = [
        HBCStateSensor(coordinator),
        HBCReasonSensor(coordinator),
    ]

    async_add_entities(entities)

class HBCSensorBase(CoordinatorEntity[HBCDataUpdateCoordinator], SensorEntity):
    """Base class for HBC sensors."""

    def __init__(self, coordinator: HBCDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry_id)},
            "name": "House Battery Control",
            "manufacturer": "HBC",
            "model": "Deterministic FSM",
        }

class HBCStateSensor(HBCSensorBase):
    """Sensor that displays the current FSM state."""

    _attr_translation_key = "hbc_state"
    _attr_unique_id = "hbc_state"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        # This will come from the FSM result stored in the coordinator data
        # For now, it might be None if FSM isn't run yet
        return self.coordinator.data.get("state", "IDLE")

class HBCReasonSensor(HBCSensorBase):
    """Sensor that displays why the current state was chosen."""

    _attr_translation_key = "hbc_reason"
    _attr_unique_id = "hbc_reason"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("reason", "Initializing...")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return {
            ATTR_PLAN_HTML: self.coordinator.data.get("plan_html", "")
        }
