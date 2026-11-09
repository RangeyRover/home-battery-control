"""Sensor platform for House Battery Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower, UnitOfTime
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
        HBCSyntheticRatesDiagnosticSensor(coordinator),
        HBCSolveTimeSensor(coordinator),
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
        return self.coordinator.data.get("state", "SELF_CONSUMPTION")


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


class HBCSyntheticRatesDiagnosticSensor(HBCSensorBase):
    """Sensor that exposes the internal state of the Synthetic Rates Predictor."""

    _attr_translation_key = "hbc_synthetic_rates_diagnostic"
    _attr_unique_id = "hbc_synthetic_rates_diagnostic"

    @property
    def native_value(self) -> str | None:
        """Return Active if we have synthetic data, Inactive otherwise."""
        if self.coordinator.data.get("synthetic_analog_days"):
            return "Active"
        return "Inactive"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full JSON serializable analog_days data and synthesized curve."""
        attrs = {}
        if self.coordinator.data.get("synthetic_analog_days"):
            attrs["analog_days"] = self.coordinator.data["synthetic_analog_days"]
            attrs["pricing_curve"] = self.coordinator.data.get("synthetic_pricing_curve", [])
        return attrs


class HBCSolveTimeSensor(HBCSensorBase):
    """Diagnostic sensor exposing LP/MIP solver execution duration and stats."""

    _attr_translation_key = "hbc_solve_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: HBCDataUpdateCoordinator) -> None:
        """Initialize the solve time diagnostic sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_hbc_solve_time"

    @property
    def native_value(self) -> float | None:
        """Return the last solve duration in seconds."""
        stats = (self.coordinator.data or {}).get("solver_stats")
        if isinstance(stats, dict) and stats.get("solve_seconds") is not None:
            return float(stats["solve_seconds"])
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return solver diagnostic attributes."""
        data = self.coordinator.data or {}
        stats = data.get("solver_stats")
        if not isinstance(stats, dict):
            return {}
        return {
            "budget_seconds": stats.get("budget_seconds"),
            "passes": stats.get("passes"),
            "integer_used": stats.get("integer_used"),
            "reference_solve": stats.get("reference_solve"),
            "outcome": stats.get("outcome"),
            "detail": stats.get("detail"),
            "horizon_steps": stats.get("horizon_steps"),
            "solve_seconds_max_24h": data.get("solve_seconds_max_24h"),
        }
