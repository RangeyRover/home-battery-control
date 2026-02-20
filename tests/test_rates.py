"""Tests for the RatesManager module.

Tests written FIRST per @speckit.implement TDD.
Spec 3.1: Separate import/export price entities from Amber Electric.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.rates import RatesManager


@pytest.fixture
def mock_hass():
    """Create a mock HA instance with states attribute."""
    hass = MagicMock()
    return hass


# --- Init (Spec 3.1: two entity IDs) ---

def test_rates_manager_init_dual_entity(mock_hass):
    """RatesManager must accept separate import and export entity IDs."""
    manager = RatesManager(mock_hass, "sensor.amber_import", "sensor.amber_export")
    assert manager._import_entity_id == "sensor.amber_import"
    assert manager._export_entity_id == "sensor.amber_export"
    assert manager.get_rates() == []


# --- Update with merged rates ---

def _make_amber_state(prices):
    """Helper: build a mock state with future_prices attribute."""
    state = MagicMock()
    state.attributes = {"future_prices": prices}
    return state


def test_rates_update_merges_import_export(mock_hass):
    """Update should merge import and export rates by matching timestamps."""
    import_prices = [
        {
            "periodType": "ACTUAL",
            "periodStart": "2025-02-20T12:00:00+00:00",
            "periodEnd": "2025-02-20T12:30:00+00:00",
            "perKwh": 25.5,
        },
    ]
    export_prices = [
        {
            "periodType": "ACTUAL",
            "periodStart": "2025-02-20T12:00:00+00:00",
            "periodEnd": "2025-02-20T12:30:00+00:00",
            "perKwh": 8.0,
        },
    ]

    mock_hass.states.get.side_effect = lambda eid: {
        "sensor.amber_import": _make_amber_state(import_prices),
        "sensor.amber_export": _make_amber_state(export_prices),
    }.get(eid)

    manager = RatesManager(mock_hass, "sensor.amber_import", "sensor.amber_export")
    manager.update()

    rates = manager.get_rates()
    assert len(rates) == 1
    assert rates[0]["import_price"] == 25.5
    assert rates[0]["export_price"] == 8.0


def test_rates_update_missing_entity(mock_hass):
    """Update with missing entity should still work with available data."""
    mock_hass.states.get.return_value = None

    manager = RatesManager(mock_hass, "sensor.missing_import", "sensor.missing_export")
    manager.update()
    assert manager.get_rates() == []


# --- Price Lookups (separate import/export) ---

def test_get_import_price_at(mock_hass):
    """get_import_price_at returns import price for a given time."""
    manager = RatesManager(mock_hass, "sensor.imp", "sensor.exp")
    t0 = datetime.fromisoformat("2025-02-20T12:00:00+00:00")
    t1 = datetime.fromisoformat("2025-02-20T12:30:00+00:00")

    manager._rates = [
        {"start": t0, "end": t1, "import_price": 25.0, "export_price": 8.0, "type": "ACTUAL"}
    ]

    assert manager.get_import_price_at(t0) == 25.0
    assert manager.get_import_price_at(t0 + timedelta(minutes=15)) == 25.0
    assert manager.get_import_price_at(t1) == 0.0  # outside range


def test_get_export_price_at(mock_hass):
    """get_export_price_at returns export price for a given time."""
    manager = RatesManager(mock_hass, "sensor.imp", "sensor.exp")
    t0 = datetime.fromisoformat("2025-02-20T12:00:00+00:00")
    t1 = datetime.fromisoformat("2025-02-20T12:30:00+00:00")

    manager._rates = [
        {"start": t0, "end": t1, "import_price": 25.0, "export_price": 8.0, "type": "ACTUAL"}
    ]

    assert manager.get_export_price_at(t0) == 8.0
    assert manager.get_export_price_at(t1) == 0.0  # outside range
