"""Tests for the WeatherManager module.

Tests written FIRST per @speckit.implement TDD.
Spec 3.3: Weather must use weather.get_forecasts service (HA 2023.9+)
          with fallback to legacy forecast attribute.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.house_battery_control.weather import WeatherManager


@pytest.fixture
def mock_hass():
    """Create a mock HA instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


# --- Spec 3.3: Service-based weather (primary method) ---

@pytest.mark.asyncio
async def test_weather_async_update_service(mock_hass):
    """async_update must call weather.get_forecasts service (spec 3.3)."""
    manager = WeatherManager(mock_hass, "weather.hewett_hourly")

    # Mock successful service response
    mock_hass.services.async_call.return_value = {
        "weather.hewett_hourly": {
            "forecast": [
                {"datetime": "2025-02-20T12:00:00+00:00", "temperature": 20.5, "condition": "sunny"},
                {"datetime": "2025-02-20T13:00:00+00:00", "temperature": 21.0, "condition": "cloudy"},
            ]
        }
    }

    await manager.async_update()

    forecast = manager.get_forecast()
    assert len(forecast) == 2
    assert forecast[0]["temperature"] == 20.5
    assert forecast[1]["condition"] == "cloudy"

    # Verify service was called correctly
    mock_hass.services.async_call.assert_called_once_with(
        "weather", "get_forecasts",
        {"entity_id": "weather.hewett_hourly", "type": "hourly"},
        blocking=True, return_response=True,
    )


# --- Spec 3.3: Attribute fallback ---

@pytest.mark.asyncio
async def test_weather_fallback_to_attribute(mock_hass):
    """When service fails, must fallback to state.attributes.forecast."""
    manager = WeatherManager(mock_hass, "weather.hewett_hourly")

    # Service call fails
    mock_hass.services.async_call.side_effect = Exception("Service not available")

    # Attribute fallback data
    mock_state = MagicMock()
    mock_state.attributes = {
        "forecast": [
            {"datetime": "2025-02-20T14:00:00+00:00", "temperature": 22.0, "condition": "sunny"},
        ]
    }
    mock_hass.states.get.return_value = mock_state

    await manager.async_update()

    forecast = manager.get_forecast()
    assert len(forecast) == 1
    assert forecast[0]["temperature"] == 22.0


# --- Missing entity ---

@pytest.mark.asyncio
async def test_weather_missing_entity(mock_hass):
    """Missing entity should result in empty forecast."""
    manager = WeatherManager(mock_hass, "weather.missing")
    mock_hass.services.async_call.side_effect = Exception("Not found")
    mock_hass.states.get.return_value = None

    await manager.async_update()
    assert manager.get_forecast() == []
