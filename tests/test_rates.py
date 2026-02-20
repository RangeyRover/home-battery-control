"""Tests for the RatesManager module.

Tests written FIRST per @speckit.implement TDD.
Spec 3.1: Separate import/export price entities from Amber Electric.
Spec 4: Timezone safety — all datetimes must be UTC-aware.
"""
from datetime import datetime, timedelta, timezone
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

def _make_amber_state(prices, key="future_prices"):
    """Helper: build a mock state with the given attribute key containing prices."""
    state = MagicMock()
    state.attributes = {key: prices}
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
        "sensor.amber_import": _make_amber_state(import_prices, key="forecast"),
        "sensor.amber_export": _make_amber_state(export_prices, key="forecast"),
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


# ============================================================
# REGRESSION: TZ-naive vs TZ-aware crash (Production 2026-02-20)
# ============================================================

def test_price_lookup_with_utc_aware_time(mock_hass):
    """REGRESSION: get_import_price_at must work with UTC-aware query time.

    Production crash: 'can't subtract offset-naive and offset-aware datetimes'
    Caused by rates having naive timestamps while coordinator passes aware dt.
    """
    manager = RatesManager(mock_hass, "sensor.imp", "sensor.exp")

    # UTC-aware timestamps (as returned by dt_util.as_utc)
    t0 = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=30)

    manager._rates = [
        {"start": t0, "end": t1, "import_price": 30.0, "export_price": 10.0, "type": "ACTUAL"}
    ]

    # Query with UTC-aware time (what coordinator actually passes)
    query_time = datetime(2025, 6, 15, 12, 10, tzinfo=timezone.utc)
    result = manager.get_import_price_at(query_time)
    assert result == 30.0


def test_rates_update_parses_amber_forecast_attribute(mock_hass):
    """Spec 3.1: Must explicitly parse the `forecast` attribute for Amber compatibility."""
    prices = [
        {
            "periodType": "FORECAST",
            "periodStart": "2025-02-20T12:00:00+00:00",
            "periodEnd": "2025-02-20T12:30:00+00:00",
            "perKwh": 10.0,
        },
    ]

    mock_hass.states.get.side_effect = lambda eid: {
        "sensor.amber_import": _make_amber_state(prices, key="forecast"),
        "sensor.amber_export": _make_amber_state([], key="forecast"),
    }.get(eid)

    manager = RatesManager(mock_hass, "sensor.amber_import", "sensor.amber_export")
    manager.update()

    rates = manager.get_rates()
    assert len(rates) == 1
    assert rates[0]["import_price"] == 10.0
    assert rates[0]["type"] == "FORECAST"

