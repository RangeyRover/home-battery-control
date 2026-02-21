"""Test the House Battery Control config flow.

Tests written FIRST per @speckit.implement TDD.
Spec 3.1: Split import/export price entities.
Spec 3.6: Control step is optional (debug mode).
"""

from custom_components.house_battery_control.const import (
    CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
    CONF_ALLOW_EXPORT_ENTITY,
    CONF_BATTERY_CAPACITY,
    CONF_BATTERY_CHARGE_RATE_MAX,
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_POWER_INVERT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_EXPORT_PRICE_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_IMPORT_PRICE_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_INVERTER_LIMIT_MAX,
    CONF_LOAD_TODAY_ENTITY,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    CONF_SOLAR_ENTITY,
    CONF_SOLCAST_TODAY_ENTITY,
    CONF_SOLCAST_TOMORROW_ENTITY,
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
        CONF_IMPORT_PRICE_ENTITY,
        CONF_EXPORT_PRICE_ENTITY,
        CONF_WEATHER_ENTITY,
        CONF_SOLCAST_TODAY_ENTITY,
        CONF_SOLCAST_TOMORROW_ENTITY,
        CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
        CONF_ALLOW_EXPORT_ENTITY,
        CONF_SCRIPT_CHARGE,
        CONF_SCRIPT_CHARGE_STOP,
        CONF_SCRIPT_DISCHARGE,
        CONF_SCRIPT_DISCHARGE_STOP,
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
        CONF_IMPORT_PRICE_ENTITY,
        CONF_EXPORT_PRICE_ENTITY,
        CONF_WEATHER_ENTITY,
        CONF_SOLCAST_TODAY_ENTITY,
        CONF_SOLCAST_TOMORROW_ENTITY,
        CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
        CONF_ALLOW_EXPORT_ENTITY,
        CONF_SCRIPT_CHARGE,
        CONF_SCRIPT_CHARGE_STOP,
        CONF_SCRIPT_DISCHARGE,
        CONF_SCRIPT_DISCHARGE_STOP,
    ]
    assert len(keys) == len(set(keys)), "Duplicate config keys detected"


def test_config_flow_class_exists():
    """ConfigFlow class should be importable."""
    from custom_components.house_battery_control.config_flow import ConfigFlow
    assert ConfigFlow is not None


def test_config_flow_has_menu_and_steps():
    """ConfigFlow should have menu, manual, yaml, energy, and control steps (S2)."""
    from custom_components.house_battery_control.config_flow import ConfigFlow
    assert hasattr(ConfigFlow, "async_step_user")
    assert hasattr(ConfigFlow, "async_step_manual")
    assert hasattr(ConfigFlow, "async_step_yaml")
    assert hasattr(ConfigFlow, "async_step_energy")
    assert hasattr(ConfigFlow, "async_step_control")


def test_config_flow_has_options():
    """ConfigFlow should support OptionsFlow for runtime reconfiguration (Spec 3.8)."""
    from custom_components.house_battery_control.config_flow import ConfigFlow
    assert hasattr(ConfigFlow, "async_get_options_flow"), "Options flow not implemented"


def test_no_tariff_entity_constant():
    """CONF_TARIFF_ENTITY should no longer exist (replaced by split rates)."""
    from custom_components.house_battery_control import const
    assert not hasattr(const, "CONF_TARIFF_ENTITY"), \
        "CONF_TARIFF_ENTITY should be removed — replaced by CONF_IMPORT/EXPORT_PRICE_ENTITY"
