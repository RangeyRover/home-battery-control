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
    prediction = await predictor.async_predict(
        start, duration_hours=1, load_entity_id="sensor.load"
    )
    assert len(prediction) == 12
    assert prediction[0]["kw"] == 0.5
    assert "start" in prediction[0]
    assert prediction[0]["start"] == start.isoformat()


@pytest.mark.asyncio
async def test_load_predict_evening_peak(mock_hass):
    """Evening peak (18:00) should be 2.5 kW base."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 18, 0, 0)
    prediction = await predictor.async_predict(
        start, duration_hours=1, load_entity_id="sensor.load"
    )
    assert prediction[0]["kw"] == 2.5


@pytest.mark.asyncio
async def test_load_predict_morning_peak(mock_hass):
    """Morning peak (08:00) should be 1.5 kW base."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 8, 0, 0)
    prediction = await predictor.async_predict(
        start, duration_hours=1, load_entity_id="sensor.load"
    )
    assert prediction[0]["kw"] == 1.5


# --- Temperature sensitivity (new) ---


@pytest.mark.asyncio
async def test_load_high_temp_increases_load(mock_hass):
    """Load should increase when temperature exceeds high threshold."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Forecast: constant 35°C (10 degrees above 25°C threshold)
    temp_forecast = [{"datetime": start, "temperature": 35.0, "condition": "sunny"}]

    prediction = await predictor.async_predict(
        start,
        temp_forecast=temp_forecast,
        high_sensitivity=0.2,  # 0.2 kW per degree
        high_threshold=25.0,
        duration_hours=1,
        load_entity_id="sensor.load",
    )

    # Base 0.5 + (35-25)*0.2 = 0.5 + 2.0 = 2.5
    assert prediction[0]["kw"] == pytest.approx(2.5, abs=0.01)


@pytest.mark.asyncio
async def test_load_low_temp_increases_load(mock_hass):
    """Load should increase when temperature drops below low threshold."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Forecast: constant 5°C (10 degrees below 15°C threshold)
    temp_forecast = [{"datetime": start, "temperature": 5.0, "condition": "cloudy"}]

    prediction = await predictor.async_predict(
        start,
        temp_forecast=temp_forecast,
        low_sensitivity=0.3,  # 0.3 kW per degree
        low_threshold=15.0,
        duration_hours=1,
        load_entity_id="sensor.load",
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
        load_entity_id="sensor.load",
    )

    # 20°C is between thresholds, so no adjustment: base 0.5
    assert prediction[0]["kw"] == 0.5


@pytest.mark.asyncio
async def test_load_never_negative(mock_hass):
    """Load prediction must never be negative."""
    predictor = LoadPredictor(mock_hass)
    # Night time (base 0.5) with mild weather — should stay positive
    start = datetime(2025, 2, 20, 3, 0, 0)
    prediction = await predictor.async_predict(
        start, duration_hours=1, load_entity_id="sensor.load"
    )
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
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State(
            "sensor.energy",
            "10.1",
            last_updated=base_past + dt.timedelta(minutes=5),
            last_changed=base_past + dt.timedelta(minutes=5),
        ),
        State(
            "sensor.energy",
            "10.3",
            last_updated=base_past + dt.timedelta(minutes=10),
            last_changed=base_past + dt.timedelta(minutes=10),
        ),
    ]

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states},
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
            "device_class": "energy",
        }
    )

    mock_state = State(
        "sensor.example_energy_kwh",
        "51.4725",
        attributes={
            "unit_of_measurement": "kWh",
            "state_class": "total_increasing",
            "device_class": "energy",
        },
        last_changed=base_past,
        last_updated=base_past,
    )

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.example_energy_kwh": [mock_state]},
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
    assert re.match(iso8601_offset_regex, state_dict["last_changed"]), (
        f"Invalid ISO 8601 string: {state_dict['last_changed']}"
    )
    assert state_dict["last_changed"].endswith(
        "+00:00"
    )  # The mock base_past was created with tzinfo=dt.timezone.utc

    # 6. Assert attributes mapping
    attrs = state_dict["attributes"]
    assert attrs["unit_of_measurement"] == "kWh"
    assert attrs["state_class"] == "total_increasing"
    assert attrs["device_class"] == "energy"


@pytest.mark.asyncio
async def test_load_linear_interpolation(mock_hass):
    """Phase 19: Verify linear interpolation logic across a time gap."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    # 10.0 at base_past, 11.0 at base_past + 10 mins.
    # At base_past + 5 mins, value should exactly be 10.5
    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State(
            "sensor.energy",
            "11.0",
            last_updated=base_past + dt.timedelta(minutes=10),
            last_changed=base_past + dt.timedelta(minutes=10),
        ),
    ]

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states},
    ):
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.energy",
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
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    # Creates a situation where:
    # 12:00 -> 10.0
    # 12:05 -> 10.5 (usage 0.5 kWh, 6.0 kW)
    # 12:10 -> 0.0 (midnight reset! usage -10.5. System should override to previous 0.5)
    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State(
            "sensor.energy",
            "10.5",
            last_updated=base_past + dt.timedelta(minutes=5),
            last_changed=base_past + dt.timedelta(minutes=5),
        ),
        State(
            "sensor.energy",
            "0.0",
            last_updated=base_past + dt.timedelta(minutes=10),
            last_changed=base_past + dt.timedelta(minutes=10),
        ),
    ]

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states},
    ):
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.energy",
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
    from unittest.mock import AsyncMock, MagicMock

    # Load JSON files
    base_dir = os.path.dirname(os.path.dirname(__file__))
    history_path = os.path.join(base_dir, "archive", "load_history.json")
    forecast_path = os.path.join(base_dir, "archive", "average_24hr_forecast.json")

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

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    # Mock last_history_raw correctly
    predictor.last_history_raw = history_raw
    predictor.testing_bypass_history = True

    prediction = await predictor.async_predict(
        start,
        duration_hours=24,
        load_entity_id="sensor.powerwall_2_home_usage",
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
            mismatches.append(
                f"Mismatch at {time_slot_str}: predicted {p['kw']:.2f}, expected {expected_kw:.2f} (diff: {diff:.2f}, tol: {tolerance:.2f})"
            )

    total = passes + failures
    pass_rate = (passes / total) * 100 if total > 0 else 0

    print(f"\\nBucket Validation: {passes}/{total} passed ({pass_rate:.1f}%)")
    if failures > 0:
        print("Top 10 Mismatches:\\n" + "\\n".join(mismatches[:10]))

    assert pass_rate >= 90.0, f"Pass rate {pass_rate:.1f}% is below 90% threshold"


@pytest.mark.asyncio
async def test_unclamped_high_load(mock_hass):
    """Verify that load prediction does not arbitrarily clamp high power draw."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    # Create a 5 min interval with 0.625 kWh delta, which equates to exactly 7.5 kW average
    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State(
            "sensor.energy",
            "10.625",
            last_updated=base_past + dt.timedelta(minutes=5),
            last_changed=base_past + dt.timedelta(minutes=5),
        )
    ]

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        return_value={"sensor.energy": mock_states},
    ):
        # We purposely omit max_load_kw here so it runs with the (currently bad) default limit
        prediction = await predictor.async_predict(
            start,
            duration_hours=1,
            load_entity_id="sensor.energy"
        )

    # In currently clamped logic, this will fail as prediction[0]["kw"] == 4.0
    # We want it to be 7.5 organically without needing the argument injected
    assert prediction[0]["kw"] == pytest.approx(7.5, abs=0.1)


# --- Temperature Delta Adjustment Tests (Feature 017) ---


@pytest.mark.asyncio
async def test_load_delta_hot_day_positive(mock_hass):
    """FR-004: History 20°C, forecast 35°C → load increased by delta × sensitivity."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Mock profile with temperature data: historical avg 20°C, base load 0.1 kWh
    mock_profile = {"12:00": {"load_kw": 0.1, "avg_temp": 20.0}}

    temp_forecast = [{"datetime": start, "temperature": 35.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 0.1 * 12 = 1.2 kW base
    # excess_hist = max(0, 20-25) = 0, excess_forecast = max(0, 35-25) = 10
    # adjustment = (10 - 0) × 0.2 = 2.0
    # total = 1.2 + 2.0 = 3.2
    assert prediction[0]["kw"] == pytest.approx(3.2, abs=0.1)


@pytest.mark.asyncio
async def test_load_delta_zero_no_adjustment(mock_hass):
    """FR-004: History 30°C, forecast 30°C → delta = 0, no adjustment."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    mock_profile = {"12:00": {"load_kw": 0.1, "avg_temp": 30.0}}

    temp_forecast = [{"datetime": start, "temperature": 30.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 1.2 kW base
    # delta = 30 - 30 = 0, adjustment = 0
    # total = 1.2
    assert prediction[0]["kw"] == pytest.approx(1.2, abs=0.1)


@pytest.mark.asyncio
async def test_load_delta_negative_reduces_load(mock_hass):
    """FR-009: History 35°C, forecast 28°C → negative delta, load reduced."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    mock_profile = {"12:00": {"load_kw": 0.3, "avg_temp": 35.0}}

    temp_forecast = [{"datetime": start, "temperature": 28.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 0.3 * 12 = 3.6 kW base
    # delta = 28 - 35 = -7, forecast 28 > threshold 25
    # adjustment = -7 × 0.2 = -1.4
    # total = 3.6 - 1.4 = 2.2
    assert prediction[0]["kw"] == pytest.approx(2.2, abs=0.1)


@pytest.mark.asyncio
async def test_load_delta_within_band_no_adjustment(mock_hass):
    """FR-006: Forecast 22°C (within 15-25 band) → no adjustment regardless of delta."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    mock_profile = {"12:00": {"load_kw": 0.1, "avg_temp": 20.0}}

    temp_forecast = [{"datetime": start, "temperature": 22.0, "condition": "cloudy"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            low_sensitivity=0.3,
            high_threshold=25.0,
            low_threshold=15.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 1.2 kW base
    # Both in band: excess_hist=0, excess_forecast=0, adj=0
    assert prediction[0]["kw"] == pytest.approx(1.2, abs=0.1)


@pytest.mark.asyncio
async def test_load_delta_history_hot_forecast_mild(mock_hass):
    """FR-004: History 30°C (above threshold), forecast 22°C (in band) → reduce load."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    mock_profile = {"12:00": {"load_kw": 0.3, "avg_temp": 30.0}}

    temp_forecast = [{"datetime": start, "temperature": 22.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 0.3 * 12 = 3.6 kW base
    # excess_hist = max(0, 30-25) = 5, excess_forecast = max(0, 22-25) = 0
    # adjustment = (0 - 5) × 0.2 = -1.0
    # total = 3.6 - 1.0 = 2.6
    assert prediction[0]["kw"] == pytest.approx(2.6, abs=0.1)
    assert prediction[0]["load_adjustment_kw"] == pytest.approx(-1.0, abs=0.01)


@pytest.mark.asyncio
async def test_load_delta_cold_snap(mock_hass):
    """FR-005: History 18°C, forecast 8°C → load increased for heating."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    mock_profile = {"12:00": {"load_kw": 0.1, "avg_temp": 18.0}}

    temp_forecast = [{"datetime": start, "temperature": 8.0, "condition": "cloudy"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            low_sensitivity=0.3,
            low_threshold=15.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 1.2 kW base
    # excess_hist_low = max(0, 15-18) = 0, excess_forecast_low = max(0, 15-8) = 7
    # adjustment = (7 - 0) × 0.3 = 2.1
    # total = 1.2 + 2.1 = 3.3
    assert prediction[0]["kw"] == pytest.approx(3.3, abs=0.1)


@pytest.mark.asyncio
async def test_load_delta_fallback_no_temp_data(mock_hass):
    """FR-008: When avg_temp is None, fall back to absolute threshold logic."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Profile WITHOUT temperature data
    mock_profile = {"12:00": {"load_kw": 0.1, "avg_temp": None}}

    temp_forecast = [{"datetime": start, "temperature": 35.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 1.2 kW base
    # No temp history → absolute fallback: (35 - 25) × 0.2 = 2.0
    # total = 1.2 + 2.0 = 3.2
    assert prediction[0]["kw"] == pytest.approx(3.2, abs=0.1)


@pytest.mark.asyncio
async def test_load_delta_floor_at_zero(mock_hass):
    """FR-009: Negative delta adjustment cannot make load negative (0.0 floor)."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    # Very small base load, massive negative delta
    mock_profile = {"12:00": {"load_kw": 0.01, "avg_temp": 40.0}}

    temp_forecast = [{"datetime": start, "temperature": 26.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.5,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    # load_kw * 12 = 0.12 kW base
    # delta = 26 - 40 = -14, forecast 26 > threshold 25
    # adjustment = -14 × 0.5 = -7.0
    # total = 0.12 - 7.0 = -6.88 → floored to 0.0
    assert prediction[0]["kw"] == 0.0


@pytest.mark.asyncio
async def test_load_prediction_includes_diagnostic_fields(mock_hass):
    """FR-010/011: Prediction output must include temp_delta and load_adjustment_kw."""
    from unittest.mock import patch

    predictor = LoadPredictor(mock_hass)
    predictor.testing_bypass_history = True
    start = datetime(2025, 2, 20, 12, 0, 0)

    mock_profile = {"12:00": {"load_kw": 0.1, "avg_temp": 20.0}}
    temp_forecast = [{"datetime": start, "temperature": 35.0, "condition": "sunny"}]

    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    with patch(
        "custom_components.house_battery_control.historical_analyzer.build_historical_profile",
        return_value=mock_profile,
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_valid_data",
        return_value=[],
    ), patch(
        "custom_components.house_battery_control.historical_analyzer.extract_temp_data",
        return_value=[],
    ):
        prediction = await predictor.async_predict(
            start,
            temp_forecast=temp_forecast,
            high_sensitivity=0.2,
            high_threshold=25.0,
            duration_hours=1,
            load_entity_id="sensor.load",
        )

    slot = prediction[0]
    # FR-010: temp_delta present and correct (35 - 20 = 15)
    assert "temp_delta" in slot
    assert slot["temp_delta"] == pytest.approx(15.0, abs=0.1)
    # FR-011: load_adjustment_kw present and correct
    # excess_hist = max(0, 20-25) = 0, excess_forecast = max(0, 35-25) = 10
    # adj = (10-0) × 0.2 = 2.0
    assert "load_adjustment_kw" in slot
    assert slot["load_adjustment_kw"] == pytest.approx(2.0, abs=0.1)


@pytest.mark.asyncio
async def test_load_prediction_diagnostic_null_without_temp_history(mock_hass):
    """FR-010: temp_delta is None when no historical temperature data."""
    predictor = LoadPredictor(mock_hass)
    start = datetime(2025, 2, 20, 12, 0, 0)

    prediction = await predictor.async_predict(
        start, duration_hours=1, load_entity_id="sensor.load"
    )

    # Fallback profile has no temp history
    assert prediction[0]["temp_delta"] is None


# --- Load History Cache Tests (Feature 020) ---


@pytest.mark.asyncio
async def test_cache_prevents_second_db_call(mock_hass):
    """TR-002: Two consecutive calls with same time — second must NOT invoke get_significant_states."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    mock_states = [
        State("sensor.load", "1.0", last_updated=base_past, last_changed=base_past),
    ]

    mock_get_states = MagicMock(return_value={"sensor.load": mock_states})

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        mock_get_states,
    ), patch(
        "homeassistant.util.dt.now",
        return_value=start,
    ):
        # First call — should fetch from recorder
        await predictor.async_predict(
            start, duration_hours=1, load_entity_id="sensor.load"
        )
        first_call_count = mock_get_states.call_count

        # Second call — cache should prevent DB call
        await predictor.async_predict(
            start, duration_hours=1, load_entity_id="sensor.load"
        )
        second_call_count = mock_get_states.call_count

    assert first_call_count >= 1, "First call should have queried the recorder"
    assert second_call_count == first_call_count, (
        f"Cache should prevent second DB call: was {first_call_count}, now {second_call_count}"
    )


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(mock_hass):
    """TR-003: Cache must expire after CACHE_TTL_MINUTES (default 360 = 6hr)."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)
    # Use default TTL (360 min = 6 hr)

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    t1 = dt.datetime(2025, 2, 20, 10, 0, 0, tzinfo=dt.timezone.utc)
    base_past = t1 - dt.timedelta(days=1)

    mock_states = [
        State("sensor.load", "1.0", last_updated=base_past, last_changed=base_past),
    ]

    mock_get_states = MagicMock(return_value={"sensor.load": mock_states})

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        mock_get_states,
    ):
        # First call at t1
        with patch("homeassistant.util.dt.now", return_value=t1):
            await predictor.async_predict(
                t1, duration_hours=1, load_entity_id="sensor.load"
            )
        count_after_first = mock_get_states.call_count

        # Call 359 min later — just within 360 min TTL, cache should hold
        t2 = t1 + dt.timedelta(minutes=359)
        with patch("homeassistant.util.dt.now", return_value=t2):
            await predictor.async_predict(
                t2, duration_hours=1, load_entity_id="sensor.load"
            )
        count_after_within = mock_get_states.call_count
        assert count_after_within == count_after_first, (
            "Cache should still be valid at 359 min with 360 min TTL"
        )

        # Call 361 min later — past 360 min TTL, cache should expire
        t3 = t1 + dt.timedelta(minutes=361)
        with patch("homeassistant.util.dt.now", return_value=t3):
            await predictor.async_predict(
                t3, duration_hours=1, load_entity_id="sensor.load"
            )
        count_after_expired = mock_get_states.call_count

    assert count_after_expired > count_after_within, (
        "Cache should have expired at 361 min with 360 min TTL — recorder should be called again"
    )


@pytest.mark.asyncio
async def test_cached_output_matches_fresh_output(mock_hass):
    """TR-004: Cached prediction must be identical to the first (fresh) prediction."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kWh"})

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    # Provide realistic history so the profile isn't just fallback
    mock_states = [
        State("sensor.energy", "10.0", last_updated=base_past, last_changed=base_past),
        State(
            "sensor.energy",
            "10.1",
            last_updated=base_past + dt.timedelta(minutes=5),
            last_changed=base_past + dt.timedelta(minutes=5),
        ),
        State(
            "sensor.energy",
            "10.3",
            last_updated=base_past + dt.timedelta(minutes=10),
            last_changed=base_past + dt.timedelta(minutes=10),
        ),
    ]

    mock_get_states = MagicMock(return_value={"sensor.energy": mock_states})

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        mock_get_states,
    ), patch(
        "homeassistant.util.dt.now",
        return_value=start,
    ):
        # Fresh fetch
        result_fresh = await predictor.async_predict(
            start, duration_hours=1, load_entity_id="sensor.energy"
        )
        # Cached fetch
        result_cached = await predictor.async_predict(
            start, duration_hours=1, load_entity_id="sensor.energy"
        )

    # Element-by-element comparison
    assert len(result_fresh) == len(result_cached), "Lengths differ"
    for i, (fresh, cached) in enumerate(zip(result_fresh, result_cached)):
        assert fresh == cached, f"Mismatch at index {i}: fresh={fresh}, cached={cached}"


@pytest.mark.asyncio
async def test_cache_metadata_exposed(mock_hass):
    """SC-004: cache_date and cache_refreshed_at are None before first call, populated after."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    # Before first call — both should be None
    assert predictor.cache_date is None
    assert predictor.cache_refreshed_at is None

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    start = dt.datetime(2025, 2, 20, 12, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    mock_states = [
        State("sensor.load", "1.0", last_updated=base_past, last_changed=base_past),
    ]

    mock_get_states = MagicMock(return_value={"sensor.load": mock_states})

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        mock_get_states,
    ), patch(
        "homeassistant.util.dt.now",
        return_value=start,
    ):
        await predictor.async_predict(
            start, duration_hours=1, load_entity_id="sensor.load"
        )

    # After first call — both should be populated
    assert predictor.cache_date is not None, "cache_date should be set after first call"
    assert predictor.cache_refreshed_at is not None, "cache_refreshed_at should be set after first call"
    assert isinstance(predictor.cache_date, dt.date)
    assert isinstance(predictor.cache_refreshed_at, dt.datetime)


@pytest.mark.asyncio
async def test_configurable_cache_ttl_respected(mock_hass):
    """TTL set on LoadPredictor must control cache expiry, not a hardcoded value."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)
    predictor.CACHE_TTL_MINUTES = 15  # 15-minute TTL

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    t1 = dt.datetime(2025, 3, 1, 10, 0, 0, tzinfo=dt.timezone.utc)
    base_past = t1 - dt.timedelta(days=1)

    mock_states = [
        State("sensor.load", "1.5", last_updated=base_past, last_changed=base_past),
    ]
    mock_get_states = MagicMock(return_value={"sensor.load": mock_states})

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        mock_get_states,
    ):
        # First call at t1
        with patch("homeassistant.util.dt.now", return_value=t1):
            await predictor.async_predict(
                t1, duration_hours=1, load_entity_id="sensor.load"
            )
        count_after_first = mock_get_states.call_count

        # Second call 10 min later — within 15 min TTL, cache should hold
        t2 = t1 + dt.timedelta(minutes=10)
        with patch("homeassistant.util.dt.now", return_value=t2):
            await predictor.async_predict(
                t2, duration_hours=1, load_entity_id="sensor.load"
            )
        count_after_cached = mock_get_states.call_count
        assert count_after_cached == count_after_first, (
            "Cache should still be valid at 10 min with 15/min TTL"
        )

        # Third call 20 min later — past 15 min TTL, cache should expire
        t3 = t1 + dt.timedelta(minutes=20)
        with patch("homeassistant.util.dt.now", return_value=t3):
            await predictor.async_predict(
                t3, duration_hours=1, load_entity_id="sensor.load"
            )
        count_after_expired = mock_get_states.call_count

    assert count_after_expired > count_after_cached, (
        "Cache should have expired at 20 min with 15 min TTL — recorder should be called again"
    )


@pytest.mark.asyncio
async def test_default_cache_ttl_is_class_constant(mock_hass):
    """LoadPredictor default TTL should be 360 minutes (6 hours)."""
    predictor = LoadPredictor(mock_hass)
    assert hasattr(predictor, "CACHE_TTL_MINUTES"), "CACHE_TTL_MINUTES must exist"
    assert predictor.CACHE_TTL_MINUTES == 360, (
        f"Default CACHE_TTL_MINUTES should be 360 (6hr), got {predictor.CACHE_TTL_MINUTES}"
    )

    # Verify TTL is overridable (as coordinator does from config)
    predictor.CACHE_TTL_MINUTES = 120
    assert predictor.CACHE_TTL_MINUTES == 120, "TTL should be overridable"


@pytest.mark.asyncio
async def test_cache_metadata_includes_history_range(mock_hass):
    """history_start and history_end must be populated after first predict call."""
    import datetime as dt
    from unittest.mock import AsyncMock, MagicMock, patch

    from homeassistant.core import State

    predictor = LoadPredictor(mock_hass)

    # Before first call — should be None
    assert predictor.history_start is None
    assert predictor.history_end is None

    async def mock_add_executor_job(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    start = dt.datetime(2025, 3, 1, 14, 0, 0, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=1)

    mock_states = [
        State("sensor.load", "2.0", last_updated=base_past, last_changed=base_past),
    ]
    mock_get_states = MagicMock(return_value={"sensor.load": mock_states})

    with patch(
        "homeassistant.components.recorder.history.get_significant_states",
        mock_get_states,
    ), patch(
        "homeassistant.util.dt.now",
        return_value=start,
    ):
        await predictor.async_predict(
            start, duration_hours=1, load_entity_id="sensor.load"
        )

    # After first call — should be populated with 5-day window
    assert predictor.history_start is not None, "history_start should be set"
    assert predictor.history_end is not None, "history_end should be set"
    expected_start = start - dt.timedelta(days=5)
    assert predictor.history_start == expected_start, (
        f"history_start should be start_time - 5 days, got {predictor.history_start}"
    )
    assert predictor.history_end == start, (
        f"history_end should be start_time, got {predictor.history_end}"
    )


@pytest.mark.asyncio
async def test_load_predictor_handles_576_steps(mock_hass):
    """Spec 037 TDD: LoadPredictor MUST support extending to 576 steps (48h)."""
    from datetime import datetime, timezone

    from custom_components.house_battery_control.load import LoadPredictor

    predictor = LoadPredictor(mock_hass)

    # In Phase 1 TDD, we verify it doesn't crash when requested to fetch or store large arrays.
    predictor._daily_base_profile = {
        f"{h:02d}:{m:02d}": {"load_kw": 1.0, "avg_temp": None}
        for h in range(24) for m in range(0, 60, 5)
    }

    start_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    predictor.testing_bypass_history = True
    mock_hass.states.get.return_value = MagicMock(attributes={"unit_of_measurement": "kW"})

    # This will fail in TDD if it's hardcapped at 288
    forecast = await predictor.async_predict(
        start_time=start_time,
        temp_forecast=None,
        high_sensitivity=0.0,
        low_sensitivity=0.0,
        duration_hours=48,
        load_entity_id="sensor.load"
    )
    assert len(forecast) == 576, f"Expected 576 steps, got {len(forecast)}"

