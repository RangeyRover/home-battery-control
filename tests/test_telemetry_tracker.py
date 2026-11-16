"""Test the Telemetry Cost Tracker module (Feature 031 & Feature 065)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.house_battery_control.const import (
    CONF_EXPORT_TODAY_ENTITY,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_TRACKER_EXPORT_PRICE,
    CONF_TRACKER_IMPORT_PRICE,
)
from custom_components.house_battery_control.telemetry_tracker import (
    TelemetryCostTracker,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config():
    """Mock the config data with the required cost tracking sensors."""
    return {
        CONF_IMPORT_TODAY_ENTITY: "sensor.import_kwh",
        CONF_EXPORT_TODAY_ENTITY: "sensor.export_kwh",
        CONF_TRACKER_IMPORT_PRICE: "sensor.amber_import",
        CONF_TRACKER_EXPORT_PRICE: "sensor.amber_export",
    }


@pytest.mark.asyncio
@patch("custom_components.house_battery_control.telemetry_tracker.Store")
async def test_tick_standard_accumulation(mock_store_class, mock_config):
    """Positive feed-in export tariff reduces cumulative cost while positive import tariff increases it."""
    mock_store_instance = AsyncMock()
    mock_store_instance.async_load.return_value = None
    mock_store_class.return_value = mock_store_instance

    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.states.get = MagicMock()

    tracker = TelemetryCostTracker(hass, mock_config)

    tracker._last_import = 10.0
    tracker._last_export = 5.0
    tracker.cumulative_cost = 100.0

    def mock_get_state(entity_id):
        state = MagicMock()
        if entity_id == "sensor.import_kwh":
            state.state = "10.5"  # 0.5 kWh imported
        elif entity_id == "sensor.export_kwh":
            state.state = "5.2"  # 0.2 kWh exported
        elif entity_id == "sensor.amber_import":
            state.state = "0.20"  # +$0.20/kWh import expense
        elif entity_id == "sensor.amber_export":
            state.state = "0.10"  # +$0.10/kWh feed-in credit
        else:
            return None
        return state

    hass.states.get.side_effect = mock_get_state

    await tracker._on_tick("dummy_time")

    # 100.0 + (0.5 * 0.20) - (0.2 * 0.10) = 100.08
    assert tracker.cumulative_cost == pytest.approx(100.08)
    assert tracker._last_import == 10.5
    assert tracker._last_export == 5.2


@pytest.mark.asyncio
@patch("custom_components.house_battery_control.telemetry_tracker.Store")
async def test_tick_negative_export_tariff_increases_cost(mock_store_class, mock_config):
    """Feature 065 (US3): Exporting into a negative feed-in tariff (-$0.06/kWh solar sponge) increases cumulative cost."""
    mock_store_instance = AsyncMock()
    mock_store_instance.async_load.return_value = None
    mock_store_class.return_value = mock_store_instance

    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.states.get = MagicMock()

    tracker = TelemetryCostTracker(hass, mock_config)
    tracker._last_import = 10.0
    tracker._last_export = 5.0
    tracker.cumulative_cost = 100.0

    def mock_get_state(entity_id):
        state = MagicMock()
        if entity_id == "sensor.import_kwh":
            state.state = "10.0"  # 0.0 kWh imported
        elif entity_id == "sensor.export_kwh":
            state.state = "6.0"  # 1.0 kWh exported
        elif entity_id == "sensor.amber_import":
            state.state = "0.02"
        elif entity_id == "sensor.amber_export":
            state.state = "-0.06"  # -$0.06/kWh solar sponge export penalty
        else:
            return None
        return state

    hass.states.get.side_effect = mock_get_state

    await tracker._on_tick("dummy_time")

    # 100.0 + (0.0 * 0.02) - (1.0 * -0.06) = 100.06
    assert tracker.cumulative_cost == pytest.approx(100.06)
    assert tracker._last_import == 10.0
    assert tracker._last_export == 6.0


@pytest.mark.asyncio
@patch("custom_components.house_battery_control.telemetry_tracker.Store")
async def test_midnight_reset_interpolation(mock_store_class, mock_config):
    """Test handling a midnight kWh reset where current < last."""
    mock_store_instance = AsyncMock()
    mock_store_instance.async_load.return_value = None
    mock_store_class.return_value = mock_store_instance

    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()

    tracker = TelemetryCostTracker(hass, mock_config)
    tracker._last_import = 15.0
    tracker._last_export = 8.0
    tracker.cumulative_cost = 200.0

    def mock_get_state(entity_id):
        state = MagicMock()
        if entity_id == "sensor.import_kwh":
            state.state = "0.3"  # Reset happened, now at 0.3
        elif entity_id == "sensor.export_kwh":
            state.state = "0.0"  # Reset happened, now at 0.0
        elif entity_id == "sensor.amber_import":
            state.state = "0.50"
        elif entity_id == "sensor.amber_export":
            state.state = "-0.10"
        return state

    hass.states.get.side_effect = mock_get_state

    await tracker._on_tick("dummy_time")

    assert tracker.cumulative_cost == pytest.approx(200.15)
    assert tracker._last_import == 0.3
    assert tracker._last_export == 0.0
