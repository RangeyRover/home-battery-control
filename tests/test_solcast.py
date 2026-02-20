"""Tests for the Solcast Solar entity-based reader.

Tests written FIRST per @speckit.implement TDD.
Spec 3.2: Solar forecast must read from Solcast HA integration entities,
          NOT call the Solcast API directly.
"""
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.solar.solcast import SolcastSolar


@pytest.fixture
def mock_hass():
    """Create a mock HA instance."""
    hass = MagicMock()
    return hass


def _make_solcast_state(detailed_forecast):
    """Build a mock state with detailedForecast attribute."""
    state = MagicMock()
    state.attributes = {"detailedForecast": detailed_forecast}
    return state


# --- Spec 3.2: Entity-based init (no API key) ---

def test_solcast_no_api_key_required(mock_hass):
    """SolcastSolar must NOT require an API key (spec 3.2)."""
    # Should construct without api_key or site_id
    solar = SolcastSolar(mock_hass)
    assert solar is not None


def test_solcast_accepts_custom_entities(mock_hass):
    """SolcastSolar must accept configurable entity IDs."""
    solar = SolcastSolar(
        mock_hass,
        forecast_today_entity="sensor.my_solcast_today",
        forecast_tomorrow_entity="sensor.my_solcast_tomorrow",
    )
    assert solar._forecast_today_entity == "sensor.my_solcast_today"
    assert solar._forecast_tomorrow_entity == "sensor.my_solcast_tomorrow"


# --- Spec 3.2: Reading from entities ---

@pytest.mark.asyncio
async def test_solcast_reads_from_entity(mock_hass):
    """Must read forecast from entity detailedForecast attribute (spec 3.2)."""
    detailed = [
        {
            "period_start": "2025-06-15T10:00:00+00:00",
            "pv_estimate": 2.5,
            "period": "PT30M",
        },
    ]

    mock_hass.states.get.side_effect = lambda eid: {
        "sensor.solcast_pv_forecast_today": _make_solcast_state(detailed),
        "sensor.solcast_pv_forecast_tomorrow": None,
    }.get(eid)

    solar = SolcastSolar(mock_hass)
    result = await solar.async_get_forecast()

    # 30-min period → 6 x 5-min slots
    assert len(result) == 6
    assert result[0]["kw"] == 2.5


@pytest.mark.asyncio
async def test_solcast_missing_entity(mock_hass):
    """Missing entities should return empty list."""
    mock_hass.states.get.return_value = None

    solar = SolcastSolar(mock_hass)
    result = await solar.async_get_forecast()
    assert result == []


@pytest.mark.asyncio
async def test_solcast_combines_today_tomorrow(mock_hass):
    """Must combine today and tomorrow forecasts."""
    today_data = [
        {
            "period_start": "2025-06-15T10:00:00+00:00",
            "pv_estimate": 2.0,
            "period": "PT30M",
        },
    ]
    tomorrow_data = [
        {
            "period_start": "2025-06-16T10:00:00+00:00",
            "pv_estimate": 3.0,
            "period": "PT30M",
        },
    ]

    mock_hass.states.get.side_effect = lambda eid: {
        "sensor.solcast_pv_forecast_today": _make_solcast_state(today_data),
        "sensor.solcast_pv_forecast_tomorrow": _make_solcast_state(tomorrow_data),
    }.get(eid)

    solar = SolcastSolar(mock_hass)
    result = await solar.async_get_forecast()

    # 6 slots today + 6 slots tomorrow = 12
    assert len(result) == 12
    # Should be sorted by time
    assert result[0]["start"] < result[-1]["start"]


@pytest.mark.asyncio
async def test_solcast_output_uses_kw_key(mock_hass):
    """Output dicts must use 'kw' key for power (spec 3.2 internal schema)."""
    detailed = [
        {
            "period_start": "2025-06-15T10:00:00+00:00",
            "pv_estimate": 1.5,
            "period": "PT30M",
        },
    ]
    mock_hass.states.get.side_effect = lambda eid: {
        "sensor.solcast_pv_forecast_today": _make_solcast_state(detailed),
        "sensor.solcast_pv_forecast_tomorrow": None,
    }.get(eid)

    solar = SolcastSolar(mock_hass)
    result = await solar.async_get_forecast()

    assert "kw" in result[0]
    assert "start" in result[0]
    assert result[0]["kw"] == 1.5
