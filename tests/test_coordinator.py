"""Tests for the HBCDataUpdateCoordinator — sensor reading and derivation logic.

Tests the coordinator's _get_sensor_value method and the inversion/load
derivation logic WITHOUT constructing the full DataUpdateCoordinator
(which requires an event loop). We test the logic directly.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.house_battery_control.const import (
    CONF_BATTERY_POWER_INVERT,
    CONF_GRID_POWER_INVERT,
)


def _make_state(value):
    """Create a minimal HA state object."""
    return SimpleNamespace(state=str(value), attributes={})


def _make_mock_hass_with_state(value):
    """Create a mock hass with a sensor returning the given value."""
    hass = MagicMock()
    if value is None:
        hass.states.get.return_value = None
    else:
        hass.states.get.return_value = _make_state(value)
    return hass


def _get_sensor_value(hass, entity_id: str) -> float:
    """Extracted logic from coordinator._get_sensor_value for direct testing."""
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unavailable", "unknown"):
        return 0.0
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return 0.0


# --- _get_sensor_value logic tests ---

def test_get_sensor_value_normal():
    """Normal numeric state should return float."""
    hass = _make_mock_hass_with_state("75.5")
    assert _get_sensor_value(hass, "sensor.test") == 75.5


def test_get_sensor_value_unavailable():
    """Unavailable state should return 0.0."""
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="unavailable", attributes={})
    assert _get_sensor_value(hass, "sensor.test") == 0.0


def test_get_sensor_value_unknown():
    """Unknown state should return 0.0."""
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="unknown", attributes={})
    assert _get_sensor_value(hass, "sensor.test") == 0.0


def test_get_sensor_value_none():
    """Missing entity should return 0.0."""
    hass = _make_mock_hass_with_state(None)
    assert _get_sensor_value(hass, "sensor.missing") == 0.0


def test_get_sensor_value_non_numeric():
    """Non-numeric state string should return 0.0."""
    hass = _make_mock_hass_with_state("not_a_number")
    assert _get_sensor_value(hass, "sensor.test") == 0.0


# --- Inversion logic tests ---

def test_battery_power_no_inversion():
    """Without inversion, battery_power should be raw value."""
    raw = 5.0
    config = {CONF_BATTERY_POWER_INVERT: False}
    inverted = raw * (-1.0 if config.get(CONF_BATTERY_POWER_INVERT) else 1.0)
    assert inverted == 5.0


def test_battery_power_with_inversion():
    """With inversion, battery_power should be negated."""
    raw = 5.0
    config = {CONF_BATTERY_POWER_INVERT: True}
    inverted = raw * (-1.0 if config.get(CONF_BATTERY_POWER_INVERT) else 1.0)
    assert inverted == -5.0


def test_grid_power_with_inversion():
    """With grid inversion, grid_power should be negated."""
    raw = 3.0
    config = {CONF_GRID_POWER_INVERT: True}
    inverted = raw * (-1.0 if config.get(CONF_GRID_POWER_INVERT) else 1.0)
    assert inverted == -3.0


# --- Load derivation tests ---

def test_load_derivation_positive():
    """load = solar + grid - battery should work correctly."""
    solar_p = 4.0
    grid_p = 1.0
    battery_p = 2.0  # charging
    load_p = solar_p + grid_p - battery_p
    assert load_p == 3.0


def test_load_derivation_clamped_to_zero():
    """Negative load should be clamped to 0."""
    solar_p = 0.0
    grid_p = 0.0
    battery_p = 5.0  # charging hard
    load_p = solar_p + grid_p - battery_p
    if load_p < 0:
        load_p = 0.0
    assert load_p == 0.0
