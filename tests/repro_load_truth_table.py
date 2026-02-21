"""Reproduction script for Phase 17 Truth Table verification."""
import datetime as dt
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from custom_components.house_battery_control.load import LoadPredictor
from homeassistant.core import HomeAssistant, State

@pytest.fixture
def mock_hass():
    mock = MagicMock(spec=HomeAssistant)
    mock.states = MagicMock()
    # Mock executor job
    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    return mock

@pytest.mark.asyncio
async def test_load_truth_table_repro(mock_hass):
    """
    Assert that the LoadPredictor produces high values (5kW+) from the user JSON, 
    matching the reported issue.
    """
    predictor = LoadPredictor(mock_hass)
    
    # Target start time (aligned with user's derived_forecast sample)
    # 2026-02-21T05:10:01+00:00 (Local Time 15:40)
    start = dt.datetime(2026, 2, 21, 5, 10, 1, tzinfo=dt.timezone.utc)
    base_past = start - dt.timedelta(days=7)
    
    # User's raw_states:
    # "35.5155" at "2026-02-15T05:40:49.986274+00:00"
    # "35.9825" at "2026-02-15T05:45:50.928423+00:00"
    # These represent 5 mins before 2026-02-21T05:10:01 local/utc etc depends on tz.
    # The user's JSON provided raw_states with dates 2026-02-15.
    # 2026-02-21 - 7 days = 2026-02-14.
    # Wait, 2026-02-21 - 6 days = 2026-02-15.
    # My code looks for exactly 7 days ago.
    
    # Let's adjust the test 'start' to be 7 days after the JSON's main data block.
    # JSON data is mostly 2026-02-15.
    # So start should be 2026-02-22.
    sim_start = dt.datetime(2026, 2, 22, 2, 30, 0, tzinfo=dt.timezone.utc)
    past_anchor = sim_start - dt.timedelta(days=7) # 2026-02-15 02:30:00
    
    mock_hass.states.get.return_value = MagicMock(
        attributes={"unit_of_measurement": "kWh"}
    )
    
    # Mock states from user JSON (subset around 02:30 - 04:00 period)
    # "15.9135" at "2026-02-15T02:29:48"
    # "16.0975" at "2026-02-15T02:30:48"
    # ...
    # "16.6095" at "2026-02-15T02:37:10"
    
    raw_json_states = [
        ("15.9135", "2026-02-15T02:29:48.427587+00:00"),
        ("16.0975", "2026-02-15T02:30:48.368987+00:00"),
        ("16.6095", "2026-02-15T02:37:10.664937+00:00"),
        ("17.1795", "2026-02-15T02:41:12.429369+00:00"),
        ("17.7595", "2026-02-15T02:46:13.556162+00:00"),
        ("18.3355", "2026-02-15T02:51:14.436147+00:00"),
        ("35.5155", "2026-02-15T05:40:49.986274+00:00"),
        ("35.9825", "2026-02-15T05:45:50.928423+00:00"),
    ]
    
    mock_states = [
        State("sensor.load", s, last_changed=dt.datetime.fromisoformat(ts))
        for s, ts in raw_json_states
    ]
    
    with patch(
        "custom_components.house_battery_control.load.history.get_significant_states",
        return_value={"sensor.load": mock_states}
    ):
        # We test the predicted slots around the high delta (05:40 - 05:45)
        # 7 days later = 2026-02-22 05:40
        test_start = dt.datetime(2026, 2, 22, 5, 40, 0, tzinfo=dt.timezone.utc)
        
        # Temp forecast to 34C (as in user table) to reproduce the additive effect
        temp_forecast = [{"datetime": test_start, "temperature": 34.0}]
        
        prediction = await predictor.async_predict(
            test_start,
            duration_hours=1,
            load_entity_id="sensor.load",
            temp_forecast=temp_forecast,
            high_sensitivity=1.0, # Default was aggressive
            high_threshold=25.0
        )
        
        # Base math for 05:40 slot:
        # Delta: 35.9825 - 35.5155 = 0.467 kWh
        # Power: 0.467 * 12 = 5.604 kW
        # Temp adjustment: (34 - 25) * 1.0 = +9.0 kW
        # Total: 14.604 kW
        
        # Current logic should produce ~14.6 kW
        assert prediction[0]["kw"] >= 10.0
        print(f"\nReproduced Predicted Load: {prediction[0]['kw']} kW")
