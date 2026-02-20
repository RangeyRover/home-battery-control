"""Tests for the RatesManager module."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.rates import RatesManager


@pytest.fixture
def mock_hass():
    """Create a mock HA instance with states attribute."""
    hass = MagicMock()
    return hass


def test_rates_manager_init(mock_hass):
    manager = RatesManager(mock_hass, "sensor.amber_general_price")
    assert manager._entity_id == "sensor.amber_general_price"
    assert manager.get_rates() == []


def test_rates_update_success(mock_hass):
    manager = RatesManager(mock_hass, "sensor.amber_general_price")

    mock_state = MagicMock()
    mock_state.attributes = {
        "future_prices": [
            {
                "periodType": "ACTUAL",
                "periodStart": "2025-02-20T12:00:00+00:00",
                "periodEnd": "2025-02-20T12:30:00+00:00",
                "perKwh": 25.5
            },
            {
                "periodType": "FORECAST",
                "periodStart": "2025-02-20T12:30:00+00:00",
                "periodEnd": "2025-02-20T13:00:00+00:00",
                "perKwh": 15.0
            }
        ]
    }
    mock_hass.states.get.return_value = mock_state

    manager.update()

    rates = manager.get_rates()
    assert len(rates) == 2
    assert rates[0]["price"] == 25.5
    assert rates[1]["price"] == 15.0
    assert rates[0]["type"] == "ACTUAL"


def test_rates_update_missing_entity(mock_hass):
    manager = RatesManager(mock_hass, "sensor.missing")
    mock_hass.states.get.return_value = None

    manager.update()
    assert manager.get_rates() == []


def test_get_price_at(mock_hass):
    manager = RatesManager(mock_hass, "sensor.amber_general_price")
    t0 = datetime.fromisoformat("2025-02-20T12:00:00+00:00")
    t1 = datetime.fromisoformat("2025-02-20T12:30:00+00:00")

    manager._rates = [
        {"start": t0, "end": t1, "price": 10.0, "type": "ACTUAL"}
    ]

    assert manager.get_price_at(t0) == 10.0
    assert manager.get_price_at(t0 + timedelta(minutes=15)) == 10.0
    assert manager.get_price_at(t1) == 0.0
    assert manager.get_price_at(t0 - timedelta(minutes=1)) == 0.0
