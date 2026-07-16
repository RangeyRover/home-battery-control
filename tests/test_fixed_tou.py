"""Tests for Fixed TOU Generator."""
from datetime import datetime
from zoneinfo import ZoneInfo

from custom_components.house_battery_control.const import (
    CONF_FIXED_TOU_EXPORT_END,
    CONF_FIXED_TOU_EXPORT_PRICE,
    CONF_FIXED_TOU_EXPORT_START,
    CONF_FIXED_TOU_IMPORT_END,
    CONF_FIXED_TOU_IMPORT_PRICE,
    CONF_FIXED_TOU_IMPORT_START,
)


def test_fixed_tou_generator_structure():
    """T007: Verify the basic structure and dynamic price lookup of the output."""
    from custom_components.house_battery_control.fixed_tou import FixedTOUGenerator

    config = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "06:00:00",
        CONF_FIXED_TOU_IMPORT_PRICE.format(1): 30.558,

        CONF_FIXED_TOU_IMPORT_START.format(2): "06:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(2): "10:00:00",
        CONF_FIXED_TOU_IMPORT_PRICE.format(2): 47.014,

        CONF_FIXED_TOU_IMPORT_START.format(3): "10:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(3): "15:00:00",
        CONF_FIXED_TOU_IMPORT_PRICE.format(3): 21.604,

        CONF_FIXED_TOU_IMPORT_START.format(4): "15:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(4): "00:00:00",
        CONF_FIXED_TOU_IMPORT_PRICE.format(4): 47.014,

        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "17:00:00",
        CONF_FIXED_TOU_EXPORT_PRICE.format(1): 1.0,

        CONF_FIXED_TOU_EXPORT_START.format(2): "17:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(2): "21:00:00",
        CONF_FIXED_TOU_EXPORT_PRICE.format(2): 27.0,

        CONF_FIXED_TOU_EXPORT_START.format(3): "21:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(3): "00:00:00",
        CONF_FIXED_TOU_EXPORT_PRICE.format(3): 1.0,
    }

    generator = FixedTOUGenerator(config)

    # Generate from a known datetime
    tz = ZoneInfo("Australia/Sydney")
    start_dt = datetime(2025, 3, 1, 10, 0, tzinfo=tz) # 10 AM local time

    forecast = generator.generate_forecast(start_dt)

    # Expected: 48 hours = 2 days, 5 min intervals = 12 * 48 = 576 blocks
    assert len(forecast) == 576

    # First block should be 10:00 AM (shoulder period, so price is 21.604, export 1.0)
    assert forecast[0]["start_time"] == start_dt
    assert forecast[0]["per_kwh"] == 21.604
    assert forecast[0]["export_price"] == 1.0

    # Verify peak period starts at 15:00
    peak_start_idx = 12 * 5 # 5 hours later = 60 blocks
    assert forecast[peak_start_idx]["per_kwh"] == 47.014
    assert forecast[peak_start_idx]["export_price"] == 1.0

    # Verify export peak starts at 17:00
    export_peak_start_idx = 12 * 7 # 7 hours later = 84 blocks
    assert forecast[export_peak_start_idx]["per_kwh"] == 47.014
    assert forecast[export_peak_start_idx]["export_price"] == 27.0

def test_fixed_tou_generator_dst_boundary():
    """T007: Verify generation across a DST boundary with dynamic periods."""
    from custom_components.house_battery_control.fixed_tou import FixedTOUGenerator

    config = {
        CONF_FIXED_TOU_IMPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(1): "12:00:00",
        CONF_FIXED_TOU_IMPORT_PRICE.format(1): 10.0,

        CONF_FIXED_TOU_IMPORT_START.format(2): "12:00:00",
        CONF_FIXED_TOU_IMPORT_END.format(2): "00:00:00",
        CONF_FIXED_TOU_IMPORT_PRICE.format(2): 40.0,

        CONF_FIXED_TOU_EXPORT_START.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_END.format(1): "00:00:00",
        CONF_FIXED_TOU_EXPORT_PRICE.format(1): 1.0,
    }
    generator = FixedTOUGenerator(config)

    tz = ZoneInfo("Australia/Sydney")
    # DST ends in Sydney on first Sunday of April (e.g., April 5, 2026, 3:00 AM local time shifts to 2:00 AM)
    start_dt = datetime(2026, 4, 4, 12, 0, tzinfo=tz)

    forecast = generator.generate_forecast(start_dt)

    assert len(forecast) == 576

    day2_1600 = datetime(2026, 4, 5, 16, 0, tzinfo=tz)
    found_peak = False
    for block in forecast:
        if block["start_time"] == day2_1600:
            found_peak = True
            assert block["per_kwh"] == 40.0
            break

    assert found_peak, "Did not find the 16:00 block on day 2"
