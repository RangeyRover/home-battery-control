import asyncio
import datetime as dt
import json
import os
import sys
import zoneinfo
from unittest.mock import AsyncMock, MagicMock

# Add the project root to sys path so we can import the component
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from custom_components.house_battery_control.load import LoadPredictor


async def main():
    print("=" * 60)
    print(" HBC FSM Prototyping Framework: Load Predictor ")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    history_path = os.path.join(base_dir, "load_history.json")

    if not os.path.exists(history_path):
        print(f"Error: Could not find {history_path}")
        return

    print("Loading historical data JSON...")
    with open(history_path, "r") as f:
        history_raw = json.load(f)

    print("Initializing Home Assistant Mocks...")
    mock_hass = MagicMock()
    async def mock_add_executor_job(func, *args):
        return func(*args)
    mock_hass.async_add_executor_job = AsyncMock(side_effect=mock_add_executor_job)
    mock_hass.states.get.return_value = MagicMock(
        attributes={"unit_of_measurement": "kWh"}
    )

    try:
        adelaide_tz = zoneinfo.ZoneInfo("Australia/Adelaide")
    except Exception:
        adelaide_tz = dt.timezone(dt.timedelta(hours=10, minutes=30))

    start = dt.datetime(2025, 1, 29, 0, 0, 0, tzinfo=adelaide_tz)

    predictor = LoadPredictor(mock_hass)
    predictor.last_history_raw = history_raw
    predictor.testing_bypass_history = True

    print("\nRunning async_predict (24-hour generation)...")
    prediction = await predictor.async_predict(
        start,
        duration_hours=24,
        load_entity_id="sensor.powerwall_2_home_usage",
        max_load_kw=10.0,
    )

    print("\n" + "=" * 45)
    print(f"| {'Time Slot':<10} | {'Predicted Power (kW)':<24} |")
    print("=" * 45)

    total_kw = 0.0
    for p in prediction:
        interval_start_dt = dt.datetime.fromisoformat(p["start"]).astimezone(adelaide_tz)
        time_slot_str = interval_start_dt.strftime("%H:%M")
        kw = p["kw"]
        total_kw += kw
        print(f"| {time_slot_str:<10} | {kw:<24.2f} |")

    print("=" * 45)
    print(f"Total buckets generated: {len(prediction)}")
    print(f"Average kW per bucket : {total_kw / len(prediction):.2f} kW")
    print("=" * 45)

if __name__ == "__main__":
    asyncio.run(main())
