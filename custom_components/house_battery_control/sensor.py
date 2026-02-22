"""Sensor platform for House Battery Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
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
        HBCLimitKwSensor(coordinator),
        HBCDpTargetSocSensor(coordinator),
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
        return {ATTR_PLAN_HTML: self.coordinator.data.get("plan_html", "")}


class HBCLimitKwSensor(HBCSensorBase):
    """Sensor that displays the raw fractional mathematical target limit for the current DP tick."""

    _attr_translation_key = "hbc_limit_kw"
    _attr_unique_id = "hbc_limit_kw"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT

    @property
    def native_value(self) -> float | None:
        """Return the precise raw limit_kw constraint sent to the physical layer."""
        return self.coordinator.data.get("limit_kw")


class HBCDpTargetSocSensor(HBCSensorBase):
    """Sensor that explicitly tracks the raw unabridged target SOC from the mathematical DP Engine."""

    _attr_translation_key = "hbc_dp_target_soc"
    _attr_unique_id = "hbc_dp_target_soc"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        """Return the target_soc constraint the engine is pathfinding on."""
        return self.coordinator.data.get("target_soc")
