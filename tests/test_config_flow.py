"""Test the House Battery Control config flow.

NOTE: Full config flow integration tests require a real HA instance.
These tests validate the flow schema and step structure using mocks.
"""

from custom_components.house_battery_control.const import (
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
    CONF_LOAD_TODAY_ENTITY,
    CONF_SOLAR_ENTITY,
    CONF_TARIFF_ENTITY,
    CONF_WEATHER_ENTITY,
)


def test_all_config_keys_are_strings():
    """All config keys must be string constants."""
    keys = [
        CONF_BATTERY_SOC_ENTITY,
        CONF_BATTERY_POWER_ENTITY,
        CONF_BATTERY_POWER_INVERT,
        CONF_SOLAR_ENTITY,
        CONF_GRID_ENTITY,
        CONF_GRID_POWER_INVERT,
        CONF_LOAD_TODAY_ENTITY,
        CONF_IMPORT_TODAY_ENTITY,
        CONF_EXPORT_TODAY_ENTITY,
        CONF_BATTERY_CAPACITY,
        CONF_BATTERY_CHARGE_RATE_MAX,
        CONF_INVERTER_LIMIT_MAX,
        CONF_TARIFF_ENTITY,
        CONF_WEATHER_ENTITY,
        CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
        CONF_ALLOW_EXPORT_ENTITY,
    ]
    for key in keys:
        assert isinstance(key, str), f"{key} is not a string"


def test_config_keys_are_unique():
    """All config keys must be unique."""
    keys = [
        CONF_BATTERY_SOC_ENTITY,
        CONF_BATTERY_POWER_ENTITY,
        CONF_BATTERY_POWER_INVERT,
        CONF_SOLAR_ENTITY,
        CONF_GRID_ENTITY,
        CONF_GRID_POWER_INVERT,
        CONF_LOAD_TODAY_ENTITY,
        CONF_IMPORT_TODAY_ENTITY,
        CONF_EXPORT_TODAY_ENTITY,
        CONF_BATTERY_CAPACITY,
        CONF_BATTERY_CHARGE_RATE_MAX,
        CONF_INVERTER_LIMIT_MAX,
        CONF_TARIFF_ENTITY,
        CONF_WEATHER_ENTITY,
        CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
        CONF_ALLOW_EXPORT_ENTITY,
    ]
    assert len(keys) == len(set(keys)), "Duplicate config keys detected"


def test_config_flow_class_exists():
    """ConfigFlow class should be importable."""
    from custom_components.house_battery_control.config_flow import ConfigFlow
    assert ConfigFlow is not None


def test_config_flow_has_three_steps():
    """ConfigFlow should have user, energy, and control steps."""
    from custom_components.house_battery_control.config_flow import ConfigFlow
    assert hasattr(ConfigFlow, "async_step_user")
    assert hasattr(ConfigFlow, "async_step_energy")
    assert hasattr(ConfigFlow, "async_step_control")
