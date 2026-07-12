"""Tests for Fixed TOU Generator."""
from datetime import datetime
from zoneinfo import ZoneInfo

# We will need the generator class. We know it will be FixedTOUGenerator in fixed_tou.py.
# The user spec expects a 48-hour continuous array of pricing blocks, structually identical to Amber dynamic forecasts.
# FR-004: Daily schedule identical all 7 days
# FR-005: Use local timezone, accounting for DST.

def test_fixed_tou_generator_structure():
    """T005: Verify the basic structure of the output."""
    from custom_components.house_battery_control.fixed_tou import FixedTOUGenerator

    # Example config data
    config = {
        "fixed_tou_peak_start": "16:00:00",
        "fixed_tou_peak_end": "20:00:00",
        "fixed_tou_peak_price": 40.0,
        "fixed_tou_offpeak_start": "00:00:00",
        "fixed_tou_offpeak_end": "06:00:00",
        "fixed_tou_offpeak_price": 10.0,
        "fixed_tou_shoulder_price": 20.0,
    }

    generator = FixedTOUGenerator(config)

    # Generate from a known datetime
    tz = ZoneInfo("Australia/Sydney")
    start_dt = datetime(2025, 3, 1, 10, 0, tzinfo=tz) # 10 AM local time

    forecast = generator.generate_forecast(start_dt)

    # Expected: 48 hours = 2 days, 5 min intervals = 12 * 48 = 576 blocks
    assert len(forecast) == 576

    # First block should be 10:00 AM (shoulder period, so price is 20)
    assert forecast[0]["start_time"] == start_dt
    assert forecast[0]["per_kwh"] == 20.0

    # Verify peak period starts at 16:00
    peak_start_idx = 12 * 6 # 6 hours later = 72 blocks
    assert forecast[peak_start_idx]["per_kwh"] == 40.0

def test_fixed_tou_generator_dst_boundary():
    """T005: Verify generation across a DST boundary."""
    from custom_components.house_battery_control.fixed_tou import FixedTOUGenerator

    config = {
        "fixed_tou_peak_start": "16:00:00",
        "fixed_tou_peak_end": "20:00:00",
        "fixed_tou_peak_price": 40.0,
        "fixed_tou_offpeak_start": "00:00:00",
        "fixed_tou_offpeak_end": "06:00:00",
        "fixed_tou_offpeak_price": 10.0,
        "fixed_tou_shoulder_price": 20.0,
    }
    generator = FixedTOUGenerator(config)

    tz = ZoneInfo("Australia/Sydney")
    # DST ends in Sydney on first Sunday of April (e.g., April 5, 2026, 3:00 AM local time shifts to 2:00 AM)
    start_dt = datetime(2026, 4, 4, 12, 0, tzinfo=tz)

    forecast = generator.generate_forecast(start_dt)

    # 48 hours means it crosses the boundary.
    # The output length should still be exactly 576 blocks (48 real elapsed hours).
    assert len(forecast) == 576

    # The timezone shifts inside the array. Verify that the peak period on day 2 is STILL at 16:00 local time
    day2_1600 = datetime(2026, 4, 5, 16, 0, tzinfo=tz)

    found_peak = False
    for block in forecast:
        if block["start_time"] == day2_1600:
            found_peak = True
            assert block["per_kwh"] == 40.0
            break

    assert found_peak, "Did not find the 16:00 block on day 2"
