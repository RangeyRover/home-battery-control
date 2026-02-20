"""Tests for the DefaultBatteryStateMachine (fsm/default.py).

Written BEFORE implementation per TDD discipline.
Tests cover: Window Discovery, State Transitions, and Look-ahead Logic.
"""
from datetime import datetime, timedelta, timezone

import pytest
from custom_components.house_battery_control.const import (
    STATE_CHARGE_GRID,
    STATE_CHARGE_SOLAR,
    STATE_DISCHARGE_HOME,
    STATE_IDLE,
    STATE_PRESERVE,
)
from custom_components.house_battery_control.fsm.base import FSMContext, FSMResult
from custom_components.house_battery_control.fsm.default import DefaultBatteryStateMachine

# --- Helpers ---

def _make_context(**overrides) -> FSMContext:
    """Build a default FSMContext, overridable per test."""
    defaults = dict(
        soc=50.0,
        solar_production=0.0,
        load_power=1.0,
        grid_voltage=240.0,
        current_price=20.0,
        forecast_solar=[],
        forecast_load=[],
        forecast_price=[],
    )
    defaults.update(overrides)
    return FSMContext(**defaults)


def _make_price_forecast(prices: list[float], start=None, interval_min=5) -> list[dict]:
    """Build a price forecast list from a simple list of floats."""
    start = start or datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = []
    for i, price in enumerate(prices):
        result.append({
            "start": start + timedelta(minutes=i * interval_min),
            "end": start + timedelta(minutes=(i + 1) * interval_min),
            "price": price,
        })
    return result


def _make_solar_forecast(values: list[float], start=None, interval_min=5) -> list[dict]:
    """Build a solar forecast list from a simple list of kW floats."""
    start = start or datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = []
    for i, kw in enumerate(values):
        result.append({
            "start": start + timedelta(minutes=i * interval_min),
            "kw": kw,
        })
    return result


@pytest.fixture
def fsm():
    return DefaultBatteryStateMachine()


# ============================================================
# 1. NEGATIVE PRICE → ALWAYS CHARGE FROM GRID
# ============================================================

def test_negative_price_charges_from_grid(fsm):
    """When current price is negative, always charge from grid."""
    ctx = _make_context(current_price=-5.0, soc=50.0)
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_CHARGE_GRID
    assert "negative" in result.reason.lower() or "price" in result.reason.lower()


def test_negative_price_charges_even_at_high_soc(fsm):
    """Negative price should charge even when SoC is high (free energy)."""
    ctx = _make_context(current_price=-10.0, soc=95.0)
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_CHARGE_GRID


# ============================================================
# 2. CHEAP WINDOW DISCOVERY → CHARGE WHEN IN CHEAPEST WINDOW
# ============================================================

def test_cheap_window_triggers_charge(fsm):
    """When current price is in the cheapest window and SoC is low, charge."""
    # Prices: current slot is cheap (5), future slots are expensive (30+)
    prices = [5.0] * 6 + [30.0] * 6 + [35.0] * 6  # 90 min forecast
    ctx = _make_context(
        current_price=5.0,
        soc=30.0,
        forecast_price=_make_price_forecast(prices),
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_CHARGE_GRID


def test_cheap_window_no_charge_when_full(fsm):
    """Even in cheap window, don't charge if battery is already full."""
    prices = [5.0] * 6 + [30.0] * 12
    ctx = _make_context(
        current_price=5.0,
        soc=98.0,
        forecast_price=_make_price_forecast(prices),
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state != STATE_CHARGE_GRID


# ============================================================
# 3. SOLAR LOOK-AHEAD → CHARGE FROM SOLAR WHEN EXCESS
# ============================================================

def test_excess_solar_charges_battery(fsm):
    """When solar > load and SoC < 100%, charge from solar."""
    ctx = _make_context(
        solar_production=4.0,
        load_power=1.5,
        soc=60.0,
        current_price=20.0,  # normal price
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_CHARGE_SOLAR


def test_solar_sunrise_awareness(fsm):
    """When solar forecast shows generation coming soon, don't grid-charge
    if SoC is moderate (solar will do it for free)."""
    # Solar forecast: 0 now, ramps up in 30 min
    solar = [0.0] * 6 + [2.0, 3.0, 4.0, 4.0, 3.0, 2.0]
    ctx = _make_context(
        soc=60.0,
        current_price=15.0,  # moderate, not cheap
        solar_production=0.0,
        forecast_solar=_make_solar_forecast(solar),
    )
    result = fsm.calculate_next_state(ctx)
    # Should NOT grid-charge — solar is coming soon
    assert result.state != STATE_CHARGE_GRID


# ============================================================
# 4. PEAK PRICE → DISCHARGE TO HOME
# ============================================================

def test_high_price_discharges_home(fsm):
    """During expensive prices, discharge battery to serve house load."""
    ctx = _make_context(
        current_price=50.0,
        soc=70.0,
        load_power=2.0,
        solar_production=0.0,
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_DISCHARGE_HOME


def test_high_price_no_discharge_when_low_soc(fsm):
    """Don't discharge if SoC is at reserve level even during peak."""
    ctx = _make_context(
        current_price=50.0,
        soc=10.0,  # Below reserve
        load_power=2.0,
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state != STATE_DISCHARGE_HOME


# ============================================================
# 5. PRESERVE → HOLD CHARGE FOR UPCOMING PEAK / LOW SOLAR
# ============================================================

def test_preserve_before_peak(fsm):
    """When a peak is coming and SoC is ok, preserve charge."""
    # Prices: 5 (cheap slots), 25 (moderate NOW), then spike to 60
    # Cheap threshold = ~5, so current price 25 is NOT cheap.
    prices = [5.0] * 6 + [25.0] * 6 + [60.0] * 12
    ctx = _make_context(
        soc=80.0,
        current_price=25.0,
        solar_production=0.0,
        load_power=1.0,
        forecast_price=_make_price_forecast(prices),
    )
    result = fsm.calculate_next_state(ctx)
    # Should preserve for the upcoming peak
    assert result.state in (STATE_PRESERVE, STATE_IDLE)


# ============================================================
# 6. IDLE → DEFAULT STATE
# ============================================================

def test_idle_when_nothing_special(fsm):
    """When conditions are normal, return IDLE."""
    ctx = _make_context(
        soc=50.0,
        current_price=20.0,
        solar_production=0.5,
        load_power=0.5,
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state in (STATE_IDLE, STATE_CHARGE_SOLAR)


# ============================================================
# 7. LOAD CONSIDERATION
# ============================================================

def test_high_load_triggers_discharge(fsm):
    """When house load is high and price is above average, discharge."""
    ctx = _make_context(
        soc=70.0,
        current_price=30.0,
        solar_production=0.0,
        load_power=5.0,  # Heavy load
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_DISCHARGE_HOME


# ============================================================
# 8. RESULT STRUCTURE
# ============================================================

def test_result_has_required_fields(fsm):
    """FSMResult must always have state, limit_kw, and reason."""
    ctx = _make_context()
    result = fsm.calculate_next_state(ctx)
    assert isinstance(result, FSMResult)
    assert isinstance(result.state, str)
    assert isinstance(result.limit_kw, float)
    assert isinstance(result.reason, str)
    assert result.limit_kw >= 0.0


def test_result_reason_is_not_empty(fsm):
    """Reason must always explain the decision."""
    ctx = _make_context()
    result = fsm.calculate_next_state(ctx)
    assert len(result.reason) > 0


# ============================================================
# 9. IMPORT_PRICE KEY COMPATIBILITY (Spec 3.1 + 3.4)
# ============================================================

def _make_import_price_forecast(prices: list[float], start=None, interval_min=5) -> list[dict]:
    """Build a price forecast using the new import_price/export_price keys."""
    start = start or datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = []
    for i, price in enumerate(prices):
        result.append({
            "start": start + timedelta(minutes=i * interval_min),
            "end": start + timedelta(minutes=(i + 1) * interval_min),
            "import_price": price,
            "export_price": price * 0.3,
        })
    return result


def test_fsm_works_with_import_price_key(fsm):
    """FSM must handle forecast_price dicts with import_price key (spec 3.1)."""
    prices = [5.0] * 6 + [30.0] * 6 + [35.0] * 6
    ctx = _make_context(
        current_price=5.0,
        soc=30.0,
        forecast_price=_make_import_price_forecast(prices),
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_CHARGE_GRID


def test_peak_detection_with_import_price_key(fsm):
    """Peak detection must work with import_price format."""
    prices = [10.0] * 12 + [60.0] * 12
    ctx = _make_context(
        current_price=50.0,
        soc=70.0,
        load_power=2.0,
        solar_production=0.0,
        forecast_price=_make_import_price_forecast(prices),
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == STATE_DISCHARGE_HOME


def test_peak_coming_soon_with_import_price_key(fsm):
    """_peak_coming_soon must work with import_price format."""
    prices = [10.0] * 6 + [25.0] * 6 + [60.0] * 12
    ctx = _make_context(
        soc=80.0,
        current_price=25.0,
        solar_production=0.0,
        load_power=1.0,
        forecast_price=_make_import_price_forecast(prices),
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state in (STATE_PRESERVE, STATE_IDLE)


# ============================================================
# 10. REGRESSION: KeyError 'price' (Production Crash 2026-02-20)
# ============================================================

def test_no_keyerror_when_price_key_missing(fsm):
    """REGRESSION: FSM must NOT crash with KeyError when forecast dicts
    have 'import_price' but NO 'price' key.

    This was the exact production failure:
      Error in HBC update cycle: 'price'
    Caused by coordinator passing rates from RatesManager (which uses
    import_price/export_price) to FSM helpers that did p['price'].
    """
    # Build forecast dicts with ONLY import_price — no 'price' key at all
    forecast = [
        {
            "start": datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=i * 5),
            "end": datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=(i + 1) * 5),
            "import_price": 25.0 + i,
            "export_price": 8.0,
            # NO "price" key — this is what caused the crash
        }
        for i in range(24)
    ]

    ctx = _make_context(
        current_price=25.0,
        soc=50.0,
        forecast_price=forecast,
    )

    # This MUST NOT raise KeyError
    result = fsm.calculate_next_state(ctx)
    assert isinstance(result, FSMResult)
    assert isinstance(result.state, str)
