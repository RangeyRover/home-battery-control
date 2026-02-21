"""Tests for the LoadPredictor module."""
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.load import LoadPredictor
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    mock = MagicMock(spec=HomeAssistant)
    mock.states = MagicMock()
    return mock


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
async def test_load_derives_power_from_energy_deltas(mock_hass):
    """Verify that LoadPredictor derives kW from kWh deltas (kWh_diff * 12)."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    # Mock the current state of the entity to have kWh unit
    mock_hass.states.get.return_value = MagicMock(
        attributes={"unit_of_measurement": "kWh"}
    )


    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State("sensor.energy", "10.1", last_updated=base_past + dt.timedelta(minutes=5), last_changed=base_past + dt.timedelta(minutes=5)),
        State("sensor.energy", "10.3", last_updated=base_past + dt.timedelta(minutes=10), last_changed=base_past + dt.timedelta(minutes=10)),
    ]

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states}
    ):
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.energy",
        )

    assert prediction[0]["kw"] == pytest.approx(1.2, abs=0.1)
    assert prediction[1]["kw"] == pytest.approx(2.4, abs=0.1)


@pytest.mark.asyncio
async def test_load_derives_history_payload_schema(mock_hass):
    """Phase 17A: Verify that the internal history fetch precisely formats exactly like the REST API payload."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    # Mock the current state to return specific attributes required by the schema
    mock_hass.states.get.return_value = MagicMock(
        attributes={
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
            "device_class": "energy"
        }
    )

    mock_state = State(
        "sensor.example_energy_kwh",
        "51.4725",
        attributes={
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
            "device_class": "energy"
        },
        last_changed=base_past,
        last_updated=base_past
    )

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.example_energy_kwh": [mock_state]}
    ):
        await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.example_energy_kwh",
        )

    # 1. Assert it populated the raw list
    assert hasattr(predictor, "last_history_raw")
    raw_payload = predictor.last_history_raw

    # 2. Assert structural list of list mapping
    assert isinstance(raw_payload, list)
    assert len(raw_payload) == 1
    assert isinstance(raw_payload[0], list)
    assert len(raw_payload[0]) == 1

    # 3. Assert exact dictionary keys from user-provided schema
    state_dict = raw_payload[0][0]
    assert "entity_id" in state_dict
    assert "state" in state_dict
    assert "last_changed" in state_dict
    assert "last_updated" in state_dict
    assert "attributes" in state_dict

    # 4. Assert values map exactly
    assert state_dict["entity_id"] == "sensor.example_energy_kwh"
    assert state_dict["state"] == "51.4725"

    # 5. Assert ISO 8601 formatting with timezone retained (no forced 'Z')
    # Use standard Python regex for ISO 8601 with offset
    import re
    iso8601_offset_regex = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
    assert re.match(iso8601_offset_regex, state_dict["last_changed"]), f"Invalid ISO 8601 string: {state_dict['last_changed']}"
    assert state_dict["last_changed"].endswith("+00:00")  # The mock base_past was created with tzinfo=dt.timezone.utc

    # 6. Assert attributes mapping
    attrs = state_dict["attributes"]
    assert attrs["unit_of_measurement"] == "kWh"
    assert attrs["state_class"] == "total_increasing"
    assert attrs["device_class"] == "energy"

@pytest.mark.asyncio
async def test_load_linear_interpolation(mock_hass):
    """Phase 19: Verify linear interpolation logic across a time gap."""
    import datetime as dt
    from unittest.mock import MagicMock, AsyncMock, patch
    from homeassistant.core import State
    
    predictor = LoadPredictor(mock_hass)
    
    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    
    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)
    
    mock_hass.states.get.return_value = MagicMock(
        attributes={"unit_of_measurement": "kWh"}
    )
    
    # 10.0 at base_past, 11.0 at base_past + 10 mins.
    # At base_past + 5 mins, value should exactly be 10.5
    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State("sensor.energy", "11.0", last_updated=base_past + dt.timedelta(minutes=10), last_changed=base_past + dt.timedelta(minutes=10))
    ]
    
    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states}
    ):
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.energy",
            max_load_kw=10.0,
        )
    
    # prediction[0] predicts 12:00 -> 12:05 based on yesterday 12:00 -> 12:05.
    # val_start = interpolate(12:00) = 10.0
    # val_end = interpolate(12:05) = 10.5
    # usage = 0.5 kWh over 5 mins
    # power = 0.5 * 12 = 6.0 kW
    assert prediction[0]["kw"] == pytest.approx(6.0, abs=0.1)

@pytest.mark.asyncio
async def test_load_midnight_reset_anomaly(mock_hass):
    """Phase 19: Verify negative deltas (midnight reset) fallback to prev usage instead of calculating negative power."""
    import datetime as dt
    from unittest.mock import MagicMock, AsyncMock, patch
    from homeassistant.core import State
    
    predictor = LoadPredictor(mock_hass)
    
    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    
    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)
    
    mock_hass.states.get.return_value = MagicMock(
        attributes={"unit_of_measurement": "kWh"}
    )
    
    # Creates a situation where:
    # 12:00 -> 10.0
    # 12:05 -> 10.5 (usage 0.5 kWh, 6.0 kW)
    # 12:10 -> 0.0 (midnight reset! usage -10.5. System should override to previous 0.5)
    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State("sensor.energy", "10.5", last_updated=base_past + dt.timedelta(minutes=5), last_changed=base_past + dt.timedelta(minutes=5)),
        State("sensor.energy", "0.0", last_updated=base_past + dt.timedelta(minutes=10), last_changed=base_past + dt.timedelta(minutes=10))
    ]
    
    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states}
    ):
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.energy",
            max_load_kw=10.0,
        )
    
    # Int1: 12:00 -> 12:05
    # usage: 0.5 kWh -> 6.0 kW
    assert prediction[0]["kw"] == pytest.approx(6.0, abs=0.1)
    
    # Int2: 12:05 -> 12:10
    # usage raw = -10.5 kWh. Fallback should grab prev_usage = 0.5 kWh -> 6.0 kW
    assert prediction[1]["kw"] == pytest.approx(6.0, abs=0.1)

@pytest.mark.asyncio
async def test_load_matches_average_24hr_forecast(mock_hass):
    """Phase 21: Verify multi-day real history interpolation against mathematical reference."""
    import datetime as dt
    import json
    import os
    import zoneinfo
    from unittest.mock import MagicMock, AsyncMock, patch
    
    # Load JSON files
    base_dir = os.path.dirname(os.path.dirname(__file__))
    history_path = os.path.join(base_dir, "load_history.json")
    forecast_path = os.path.join(base_dir, "average_24hr_forecast.json")
    
    with open(history_path, "r") as f:
        history_raw = json.load(f)
    with open(forecast_path, "r") as f:
        forecast_ref = json.load(f)
        
    predictor = LoadPredictor(mock_hass)
    
    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    
    # Needs to match the start date of the simulated target day. 
    # Use Adelaide time for direct comparison with time_slots.
    try:
        adelaide_tz = zoneinfo.ZoneInfo("Australia/Adelaide")
    except zoneinfo.ZoneInfoNotFoundError:
        # Fallback if system doesn't have the tz DB handy
        adelaide_tz = dt.timezone(dt.timedelta(hours=10, minutes=30))

    # Choosing Jan 29 which is immediately after the dataset
    start = dt.datetime(2025, 1, 29, 0, 0, 0, tzinfo=adelaide_tz)
    
    mock_hass.states.get.return_value = MagicMock(
        attributes={"unit_of_measurement": "kWh"}
    )
    
    # Mock last_history_raw correctly
    predictor.last_history_raw = history_raw
    predictor.testing_bypass_history = True
    
    prediction = await predictor.async_predict(
        start,
        duration_hours=24,
        load_entity_id="sensor.powerwall_2_home_usage",
        max_load_kw=10.0,
    )
    
    # Ensure there are exactly 288 predictions
    assert len(prediction) == 288
    
    # Create lookup dict from forecast reference
    ref_dict = {item["time_slot"]: item for item in forecast_ref}
    
    passes = 0
    failures = 0
    mismatches = []
    
    for p in prediction:
        interval_start_dt = dt.datetime.fromisoformat(p["start"]).astimezone(adelaide_tz)
        time_slot_str = interval_start_dt.strftime("%H:%M")
        
        # Handle cases where the dictionary might not perfectly align
        if time_slot_str not in ref_dict:
            failures += 1
            mismatches.append(f"Missing time slot {time_slot_str} in reference")
            continue
            
        ref = ref_dict[time_slot_str]
        expected_kwh = ref["avg_kwh_usage"]
        expected_kw = expected_kwh * 12.0
        
        diff = abs(p["kw"] - expected_kw)
        
        # 10% tolerance of the expected mathematical value
        tolerance = expected_kw * 0.10
        # If expected is 0, allow a tiny floor to prevent float-rounding failures
        if tolerance < 0.05:
            tolerance = 0.05
            
        if diff <= tolerance:
            passes += 1
        else:
            failures += 1
            mismatches.append(f"Mismatch at {time_slot_str}: predicted {p['kw']:.2f}, expected {expected_kw:.2f} (diff: {diff:.2f}, tol: {tolerance:.2f})")

    total = passes + failures
    pass_rate = (passes / total) * 100 if total > 0 else 0
    
    print(f"\\nBucket Validation: {passes}/{total} passed ({pass_rate:.1f}%)")
    if failures > 0:
        print(f"Top 10 Mismatches:\\n" + "\\n".join(mismatches[:10]))
        
    assert pass_rate >= 90.0, f"Pass rate {pass_rate:.1f}% is below 90% threshold"

