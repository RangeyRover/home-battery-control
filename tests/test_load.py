"""Tests for the LoadPredictor module."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.load import LoadPredictor
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    return MagicMock(spec=HomeAssistant)


# --- Existing behaviour (revalidated) ---

@pytest.mark.asyncio
async def test_load_predict_basic(mock_hass):
    """Base load at midday should be 0.5 kW."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)
    prediction = await predictor.async_predict(start, duration_hours=1)
    assert len(prediction) == 12
    assert prediction[0]["kw"] == 0.5
    assert "start" in prediction[0]
    assert prediction[0]["start"] == start.isoformat()


@pytest.mark.asyncio
async def test_load_predict_evening_peak(mock_hass):
    """Evening peak (18:00) should be 2.5 kW base."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 18, 0, 0)
    prediction = await predictor.async_predict(start, duration_hours=1)
    assert prediction[0]["kw"] == 2.5


@pytest.mark.asyncio
async def test_load_predict_morning_peak(mock_hass):
    """Morning peak (08:00) should be 1.5 kW base."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 8, 0, 0)
    prediction = await predictor.async_predict(start, duration_hours=1)
    assert prediction[0]["kw"] == 1.5


# --- Temperature sensitivity (new) ---

@pytest.mark.asyncio
async def test_load_high_temp_increases_load(mock_hass):
    """Load should increase when temperature exceeds high threshold."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Forecast: constant 35°C (10 degrees above 25°C threshold)
    temp_forecast = [
        {"datetime": start, "temperature": 35.0, "condition": "sunny"}
    ]

    prediction = await predictor.async_predict(
        start,
        temp_forecast=temp_forecast,
        high_sensitivity=0.2,  # 0.2 kW per degree
        high_threshold=25.0,
        duration_hours=1,
    )

    # Base 0.5 + (35-25)*0.2 = 0.5 + 2.0 = 2.5
    assert prediction[0]["kw"] == pytest.approx(2.5, abs=0.01)


@pytest.mark.asyncio
async def test_load_low_temp_increases_load(mock_hass):
    """Load should increase when temperature drops below low threshold."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Forecast: constant 5°C (10 degrees below 15°C threshold)
    temp_forecast = [
        {"datetime": start, "temperature": 5.0, "condition": "cloudy"}
    ]

    prediction = await predictor.async_predict(
        start,
        temp_forecast=temp_forecast,
        low_sensitivity=0.3,  # 0.3 kW per degree
        low_threshold=15.0,
        duration_hours=1,
    )

    # Base 0.5 + (15-5)*0.3 = 0.5 + 3.0 = 3.5
    assert prediction[0]["kw"] == pytest.approx(3.5, abs=0.01)


@pytest.mark.asyncio
async def test_load_no_forecast_defaults_mild(mock_hass):
    """With no forecast, temp defaults to 20°C (no adjustment)."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)

    prediction = await predictor.async_predict(
        start,
        temp_forecast=None,
        high_sensitivity=0.5,
        low_sensitivity=0.5,
        high_threshold=25.0,
        low_threshold=15.0,
        duration_hours=1,
    )

    # 20°C is between thresholds, so no adjustment: base 0.5
    assert prediction[0]["kw"] == 0.5


@pytest.mark.asyncio
async def test_load_never_negative(mock_hass):
    """Load prediction must never be negative."""
    predictor = LoadPredictor(mock_hass)
    # Night time (base 0.5) with mild weather — should stay positive
    start = datetime(2025, 2, 20, 3, 0, 0)
    prediction = await predictor.async_predict(start, duration_hours=1)
    assert all(v["kw"] >= 0.0 for v in prediction)


# --- History Data Tests (New) ---

@pytest.mark.asyncio
async def test_load_predict_uses_past_week_history(mock_hass):
    """Spec 3.4: load predictor uses history from exact same time 7 days ago."""
    import datetime as dt
    from unittest.mock import AsyncMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    # Mock executor job to just await what's passed if it's async, or call it
    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)

    # Mock history returns state objects
    mock_states = [
        State("sensor.load", "1.75", last_updated=start - dt.timedelta(days=7)),
    ]

    with patch(
        "custom_components.house_battery_control.load.history.get_significant_states",
        return_value={"sensor.load": mock_states}
    ):
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.load"
        )

    # Base load from history = 1.75
    assert prediction[0]["kw"] == 1.75
