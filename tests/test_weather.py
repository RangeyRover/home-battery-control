"""Tests for the WeatherManager module."""
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.weather import WeatherManager


@pytest.fixture
def mock_hass():
    """Create a mock HA instance with states attribute."""
    hass = MagicMock()
    return hass


def test_weather_update(mock_hass):
    manager = WeatherManager(mock_hass, "weather.home")

    mock_state = MagicMock()
    mock_state.attributes = {
        "forecast": [
            {"datetime": "2025-02-20T12:00:00+00:00", "temperature": 20.5, "condition": "sunny"},
            {"datetime": "2025-02-20T13:00:00+00:00", "temperature": 21.0, "condition": "cloudy"}
        ]
    }
    mock_hass.states.get.return_value = mock_state

    manager.update()

    forecast = manager.get_forecast()
    assert len(forecast) == 2
    assert forecast[0]["temperature"] == 20.5
    assert forecast[1]["condition"] == "cloudy"


def test_weather_update_missing(mock_hass):
    manager = WeatherManager(mock_hass, "weather.missing")
    mock_hass.states.get.return_value = None
    manager.update()
    assert manager.get_forecast() == []
