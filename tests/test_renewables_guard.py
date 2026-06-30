"""Tests for the RenewablesGuard module."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

try:
    from custom_components.house_battery_control.renewables_guard import RenewablesGuard
except ImportError:
    RenewablesGuard = None


@pytest.fixture
def mock_hass():
    return MagicMock()


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_activates_below_threshold():
    """T011: avg renewables 4.9% -> guard active, triggers=['renewables']"""
    guard = RenewablesGuard()
    rates = [{"renewables": 4.9}] * 144
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is True
    assert guard.is_active is True
    assert "Amber Express" in guard.trigger_reasons[0]


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_inactive_above_threshold():
    """T012: avg renewables 65% -> guard inactive"""
    guard = RenewablesGuard()
    rates = [{"renewables": 65.0}] * 144
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is False
    assert guard.is_active is False


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_hysteresis_no_deactivate_at_35():
    """T013: guard active, next cycle renewables 35% -> stays active"""
    guard = RenewablesGuard()
    rates = [{"renewables": 20.0}] * 144
    guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert guard.is_active is True

    rates = [{"renewables": 35.0}] * 144
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is True


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_deactivates_above_40():
    """T014: guard active, next cycle renewables 42% -> deactivates"""
    guard = RenewablesGuard()
    rates = [{"renewables": 20.0}] * 144
    guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert guard.is_active is True

    rates = [{"renewables": 42.0}] * 144
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is False


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_no_amber_express_data():
    """T015: None renewables timeline -> guard inactive (fail-safe)"""
    guard = RenewablesGuard()
    # Missing 'renewables' key entirely in rates
    rates = [{"price": 10.0}] * 144
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    # Solcast is 100 > target, so that doesn't trigger either
    assert active is False
    assert guard.renewables_avg is None


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_empty_renewables():
    """T016: empty list -> guard inactive"""
    guard = RenewablesGuard()
    active = guard.evaluate([], 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is False
    assert guard.renewables_avg is None


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_partial_forecast_data():
    """T017: fewer than 12h of forecast intervals available -> averages across all available intervals"""
    guard = RenewablesGuard()
    rates = [{"renewables": 20.0}] * 48  # Only 4 hours
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is True
    assert guard.renewables_avg == 20.0


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_or_mode_renewables_only():
    """T018: low renewables + high solar -> active (OR mode)"""
    guard = RenewablesGuard()
    rates = [{"renewables": 20.0}] * 144
    active = guard.evaluate(rates, 100.0, "OR", 30.0, 50.0, 40.0)
    assert active is True


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_or_mode_solar_only():
    """T019: high renewables + low solar -> active (OR mode)"""
    guard = RenewablesGuard()
    rates = [{"renewables": 100.0}] * 144
    active = guard.evaluate(rates, 10.0, "OR", 30.0, 50.0, 40.0)
    assert active is True


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_and_mode_both_required():
    """T020: low renewables + high solar -> inactive (AND mode)"""
    guard = RenewablesGuard()
    rates = [{"renewables": 20.0}] * 144
    active = guard.evaluate(rates, 100.0, "AND", 30.0, 50.0, 40.0)
    assert active is False


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_and_mode_both_fire():
    """T021: low renewables + low tomorrow solar + low today solar -> active (AND mode)"""
    guard = RenewablesGuard()
    rates = [{"renewables": 20.0}] * 144
    active = guard.evaluate(rates, 10.0, "AND", 30.0, 50.0, 40.0, solcast_today=10.0)
    assert active is True


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_resolve_deadlines_today_only():
    """T024: 24h rates timeline -> correctly finds step indices for 05:00 and 15:00"""
    guard = RenewablesGuard()
    base_time = datetime(2025, 6, 15, 0, 0, tzinfo=timezone.utc)
    from datetime import timedelta
    rates = [{"start": base_time + timedelta(minutes=5*i)} for i in range(288)]
    # 05:00 is 5h = 300m = step 60. 15:00 is 15h = 900m = step 180.
    # Assuming base_time is midnight local time for simplicity in this test
    # Wait, the method converts to local time. Let's make base_time local time.
    # Wait, if base_time is UTC and local time is UTC+10 (AEST) or something...
    # To avoid local timezone issues in tests, let's patch dt_util.as_local to return the same time
    import homeassistant.util.dt as dt_util
    original_as_local = dt_util.as_local
    dt_util.as_local = lambda dt: dt  # mock as_local to do nothing

    deadlines = guard.resolve_deadline_steps(rates, ["05:00", "15:00"], base_time)
    dt_util.as_local = original_as_local

    assert deadlines == [60, 180]


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_resolve_deadlines_48h():
    """T025: 48h rates timeline -> finds 4 step indices (today 05:00+15:00, tomorrow 05:00+15:00)"""
    guard = RenewablesGuard()
    base_time = datetime(2025, 6, 15, 0, 0, tzinfo=timezone.utc)
    from datetime import timedelta
    # 576 steps for 48h. The solver only supports up to 288 for deadline injection though.
    # Wait, `resolve_deadline_steps` is constrained to 288 in my code: `if i >= 288: break`.
    # Let's fix that so it can return indices up to 288, but what about indices > 288?
    # Spec says solver targets BOTH today and tomorrow if 48h available.
    # I need to verify `resolve_deadline_steps` returns the tomorrow ones too (e.g. 60+288 = 348)
    # The solver will handle bounds up to its horizon length.
    rates = [{"start": base_time + timedelta(minutes=5*i)} for i in range(576)]

    import homeassistant.util.dt as dt_util
    original_as_local = dt_util.as_local
    dt_util.as_local = lambda dt: dt
    deadlines = guard.resolve_deadline_steps(rates, ["05:00", "15:00"], base_time)
    dt_util.as_local = original_as_local

    assert 60 in deadlines
    assert 180 in deadlines
    assert 60 + 288 in deadlines
    assert 180 + 288 in deadlines


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_resolve_deadlines_past_deadline():
    """T026: current time is 08:00, only tomorrow's 05:00 is resolved"""
    guard = RenewablesGuard()
    base_time = datetime(2025, 6, 15, 8, 0, tzinfo=timezone.utc)
    from datetime import timedelta
    rates = [{"start": base_time + timedelta(minutes=5*i)} for i in range(576)]

    import homeassistant.util.dt as dt_util
    original_as_local = dt_util.as_local
    dt_util.as_local = lambda dt: dt
    deadlines = guard.resolve_deadline_steps(rates, ["05:00", "15:00"], base_time)
    dt_util.as_local = original_as_local

    # 08:00 is t=0.
    # Today's 05:00 is in the past, so we don't hit it in the loop since the loop starts at 08:00.
    # 15:00 is 7 hours away (7*12 = 84)
    # Tomorrow's 05:00 is 21 hours away (21*12 = 252)
    assert deadlines == [84, 252, 84+288, 252+288]


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_resolve_deadlines_custom_times():
    """T027: deadline at 04:00 and 14:00 -> correct step indices"""
    guard = RenewablesGuard()
    base_time = datetime(2025, 6, 15, 0, 0, tzinfo=timezone.utc)
    from datetime import timedelta
    rates = [{"start": base_time + timedelta(minutes=5*i)} for i in range(288)]

    import homeassistant.util.dt as dt_util
    original_as_local = dt_util.as_local
    dt_util.as_local = lambda dt: dt
    deadlines = guard.resolve_deadline_steps(rates, ["04:00", "14:00"], base_time)
    dt_util.as_local = original_as_local

    assert deadlines == [48, 168]


# ── Feature 056: Solar Today Guard Tests ──────────────────────────────


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_today_solar_triggers_alone():
    """T001-056: low today (5 kWh), high tomorrow (35 kWh), high renewables (65%), OR → guard active."""
    guard = RenewablesGuard()
    rates = [{"renewables": 65.0}] * 144
    active = guard.evaluate(
        rates, solcast_tomorrow=35.0, solcast_today=5.0,
        trigger_mode="OR", renewables_threshold=30.0,
        solcast_threshold=50.0, peak_solar=40.0,
    )
    assert active is True
    assert any("Solcast Today" in r for r in guard.trigger_reasons)


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_today_solar_high_no_trigger():
    """T002-056: high today (35 kWh), high tomorrow, high renewables → guard NOT active."""
    guard = RenewablesGuard()
    rates = [{"renewables": 65.0}] * 144
    active = guard.evaluate(
        rates, solcast_tomorrow=35.0, solcast_today=35.0,
        trigger_mode="OR", renewables_threshold=30.0,
        solcast_threshold=50.0, peak_solar=40.0,
    )
    assert active is False


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_and_mode_all_three_required():
    """T003-056: AND mode, all three low → guard active with 3 reasons."""
    guard = RenewablesGuard()
    rates = [{"renewables": 5.0}] * 144
    active = guard.evaluate(
        rates, solcast_tomorrow=5.0, solcast_today=5.0,
        trigger_mode="AND", renewables_threshold=30.0,
        solcast_threshold=50.0, peak_solar=40.0,
    )
    assert active is True
    assert len(guard.trigger_reasons) == 3


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_and_mode_today_high_blocks():
    """T004-056: AND mode, today high but others low → guard NOT active."""
    guard = RenewablesGuard()
    rates = [{"renewables": 5.0}] * 144
    active = guard.evaluate(
        rates, solcast_tomorrow=5.0, solcast_today=35.0,
        trigger_mode="AND", renewables_threshold=30.0,
        solcast_threshold=50.0, peak_solar=40.0,
    )
    assert active is False


@pytest.mark.skipif(RenewablesGuard is None, reason="RenewablesGuard not implemented")
def test_guard_or_mode_today_only():
    """T005-056: OR mode, only today fires → guard active."""
    guard = RenewablesGuard()
    rates = [{"renewables": 65.0}] * 144
    active = guard.evaluate(
        rates, solcast_tomorrow=100.0, solcast_today=5.0,
        trigger_mode="OR", renewables_threshold=30.0,
        solcast_threshold=50.0, peak_solar=40.0,
    )
    assert active is True
    assert any("Solcast Today" in r for r in guard.trigger_reasons)
    assert not any("Solcast Tomorrow" in r for r in guard.trigger_reasons)
