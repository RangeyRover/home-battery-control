"""Test the House Battery Control config flow.

Tests written FIRST per @speckit.implement TDD.
Spec 3.1: Split import/export price entities.
Spec 3.6: Control step is optional (debug mode).
"""

import pytest
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
    CONF_FIXED_TOU_EXPORT_END,
    CONF_FIXED_TOU_EXPORT_START,
    CONF_FIXED_TOU_IMPORT_END,
    CONF_FIXED_TOU_IMPORT_START,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_IMPORT_PRICE_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_INVERTER_LIMIT_MAX,
    CONF_LOAD_TODAY_ENTITY,
    CONF_PANEL_ADMIN_ONLY,
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
        CONF_PANEL_ADMIN_ONLY,
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
        CONF_PANEL_ADMIN_ONLY,
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

    assert not hasattr(const, "CONF_TARIFF_ENTITY"), (
        "CONF_TARIFF_ENTITY should be removed — replaced by CONF_IMPORT/EXPORT_PRICE_ENTITY"
    )


def test_options_control_has_panel_visibility():
    """Options control step schema must include CONF_PANEL_ADMIN_ONLY (FR-001)."""
    import inspect

    from custom_components.house_battery_control.config_flow import HBCOptionsFlowHandler

    source = inspect.getsource(HBCOptionsFlowHandler.async_step_control)
    assert "CONF_PANEL_ADMIN_ONLY" in source, (
        "Options control step must include panel_admin_only toggle"
    )
    assert "BooleanSelector" in source, (
        "Panel visibility must use BooleanSelector"
    )


@pytest.mark.asyncio
async def test_config_flow_guard_fields_present():
    """T040: [US4] Verify control step schema includes guard fields."""
    from custom_components.house_battery_control.config_flow import HBCOptionsFlowHandler
    from custom_components.house_battery_control.const import (
        CONF_GUARD_DAYTIME_DEADLINE,
        CONF_GUARD_LOW_SOLAR_THRESHOLD,
        CONF_GUARD_OVERNIGHT_DEADLINE,
        CONF_GUARD_PEAK_SOLAR,
        CONF_GUARD_RENEWABLES_THRESHOLD,
        CONF_GUARD_TRIGGER_MODE,
    )

    class MockConfigEntry:
        options = {}
        data = {}

    handler = HBCOptionsFlowHandler(MockConfigEntry())
    result = await handler.async_step_control()

    # Extract keys from voluptuous schema
    schema_keys = [k.schema for k in result["data_schema"].schema.keys()]

    assert CONF_GUARD_RENEWABLES_THRESHOLD in schema_keys
    assert CONF_GUARD_LOW_SOLAR_THRESHOLD in schema_keys
    assert CONF_GUARD_PEAK_SOLAR in schema_keys
    assert CONF_GUARD_TRIGGER_MODE in schema_keys
    assert CONF_GUARD_OVERNIGHT_DEADLINE in schema_keys
    assert CONF_GUARD_DAYTIME_DEADLINE in schema_keys


@pytest.mark.asyncio
async def test_config_flow_guard_values_saved():
    """T041: [US4] Submit guard settings and verify they are stored."""
    import unittest.mock as mock

    from custom_components.house_battery_control.config_flow import HBCOptionsFlowHandler
    from custom_components.house_battery_control.const import (
        CONF_GUARD_DAYTIME_DEADLINE,
        CONF_GUARD_LOW_SOLAR_THRESHOLD,
        CONF_GUARD_OVERNIGHT_DEADLINE,
        CONF_GUARD_PEAK_SOLAR,
        CONF_GUARD_RENEWABLES_THRESHOLD,
        CONF_GUARD_TRIGGER_MODE,
    )

    class MockConfigEntry:
        options = {}
        data = {}
        entry_id = "test_entry_id"

    config_entry = MockConfigEntry()
    handler = HBCOptionsFlowHandler(config_entry)
    handler.hass = mock.MagicMock()
    # Mock the handler attribute so config_entry property resolves
    handler.handler = mock.MagicMock()
    handler.handler.config_entry_id = config_entry.entry_id
    handler.hass.config_entries.async_get_known_entry.return_value = config_entry

    user_input = {
        CONF_GUARD_RENEWABLES_THRESHOLD: 35.0,
        CONF_GUARD_LOW_SOLAR_THRESHOLD: 60.0,
        CONF_GUARD_PEAK_SOLAR: 45.0,
        CONF_GUARD_TRIGGER_MODE: "AND",
        CONF_GUARD_OVERNIGHT_DEADLINE: "06:00:00",
        CONF_GUARD_DAYTIME_DEADLINE: "14:00:00",
    }

    result = await handler.async_step_control(user_input)

    # async_create_entry returns type=create_entry with empty data,
    # but the guard values are persisted in handler._data via async_update_entry.
    assert result["type"] == "create_entry"
    assert handler._data[CONF_GUARD_RENEWABLES_THRESHOLD] == 35.0
    assert handler._data[CONF_GUARD_LOW_SOLAR_THRESHOLD] == 60.0
    assert handler._data[CONF_GUARD_PEAK_SOLAR] == 45.0
    assert handler._data[CONF_GUARD_TRIGGER_MODE] == "AND"
    assert handler._data[CONF_GUARD_DAYTIME_DEADLINE] == "14:00:00"


@pytest.mark.asyncio
async def test_config_flow_pricing_mode_amber():
    """T003: [US1] Selecting Amber Dynamic transitions to energy step."""
    import unittest.mock as mock

    from custom_components.house_battery_control.config_flow import HBCOptionsFlowHandler
    from custom_components.house_battery_control.const import (
        CONF_PRICING_MODE,
        PRICING_MODE_AMBER,
    )

    class MockConfigEntry:
        options = {}
        data = {}
        entry_id = "test_entry_id"

    config_entry = MockConfigEntry()
    handler = HBCOptionsFlowHandler(config_entry)
    handler.hass = mock.MagicMock()
    handler.handler = mock.MagicMock()
    handler.handler.config_entry_id = config_entry.entry_id
    handler.hass.config_entries.async_get_known_entry.return_value = config_entry

    user_input = {CONF_PRICING_MODE: PRICING_MODE_AMBER}
    result = await handler.async_step_pricing_mode(user_input)

    assert result["type"] == "form"
    assert result["step_id"] == "energy"


@pytest.mark.asyncio
async def test_config_flow_pricing_mode_fixed_tou():
    """T003: [US1] Selecting Fixed TOU transitions to fixed_tou step."""
    import unittest.mock as mock

    from custom_components.house_battery_control.config_flow import HBCOptionsFlowHandler
    from custom_components.house_battery_control.const import (
        CONF_PRICING_MODE,
        PRICING_MODE_FIXED_TOU,
    )

    class MockConfigEntry:
        options = {}
        data = {}
        entry_id = "test_entry_id"

    config_entry = MockConfigEntry()
    handler = HBCOptionsFlowHandler(config_entry)
    handler.hass = mock.MagicMock()
    handler.handler = mock.MagicMock()
    handler.handler.config_entry_id = config_entry.entry_id
    handler.hass.config_entries.async_get_known_entry.return_value = config_entry

    user_input = {CONF_PRICING_MODE: PRICING_MODE_FIXED_TOU}
    result = await handler.async_step_pricing_mode(user_input)

    assert result["type"] == "form"
    assert result["step_id"] == "fixed_tou"


def test_validate_fixed_tou_periods_valid():
    """T003: [US1] Validation passes for valid 24h continuous periods."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods

    user_input = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "06:00:00",
        CONF_FIXED_TOU_IMPORT_START.format(2): "06:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(2): "16:00:00",
        CONF_FIXED_TOU_IMPORT_START.format(3): "16:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(3): "00:00:00",

        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
    }

    assert validate_fixed_tou_periods(user_input) is None

def test_validate_fixed_tou_periods_missing():
    """T003: [US1] Validation fails if no periods are defined."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods
    assert validate_fixed_tou_periods({}) == "missing_periods"

def test_validate_fixed_tou_periods_invalid_start():
    """T003: [US1] Validation fails if periods do not start at 00:00."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods
    user_input = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "06:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
    }
    assert validate_fixed_tou_periods(user_input) == "invalid_period_start"

def test_validate_fixed_tou_periods_invalid_end():
    """T003: [US1] Validation fails if periods do not end at 00:00."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods
    user_input = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "23:59:00",
        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
    }
    assert validate_fixed_tou_periods(user_input) == "invalid_period_end"

def test_validate_fixed_tou_periods_gap():
    """T003: [US1] Validation fails if there is a gap."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods
    user_input = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "12:00:00",
        CONF_FIXED_TOU_IMPORT_START.format(2): "13:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(2): "00:00:00",
        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
    }
    assert validate_fixed_tou_periods(user_input) == "period_gap_or_overlap"

def test_validate_fixed_tou_periods_overlap():
    """T003: [US1] Validation fails if periods overlap."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods
    user_input = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "14:00:00",
        CONF_FIXED_TOU_IMPORT_START.format(2): "13:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(2): "00:00:00",
        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
    }
    assert validate_fixed_tou_periods(user_input) == "period_gap_or_overlap"

def test_validate_fixed_tou_periods_midnight_cross():
    """T003: [US1] Validation fails if a period crosses midnight (must be split)."""
    from custom_components.house_battery_control.config_flow import validate_fixed_tou_periods
    user_input = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "15:00:00",
        CONF_FIXED_TOU_IMPORT_START.format(2): "15:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(2): "02:00:00", # Crosses midnight
        CONF_FIXED_TOU_IMPORT_START.format(3): "02:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(3): "00:00:00",
        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
    }
    assert validate_fixed_tou_periods(user_input) == "period_crosses_midnight"

