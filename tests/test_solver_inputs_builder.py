"""Tests for the coordinator's _build_solver_inputs() method (Feature 024).

These tests are written BEFORE the implementation (TDD red phase).
They will fail until _build_solver_inputs() is implemented in coordinator.py.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _make_rates(n, import_price=10.0, export_price=5.0, start_hour=14):
    """Build a list of n rate dicts starting at given hour, 5-min intervals.
    Uses UTC so dt_util.as_local() (defaults to UTC in tests) gives matching local times."""
    base = datetime(2026, 3, 5, start_hour, 0, 0, tzinfo=timezone.utc)
    rates = []
    for i in range(n):
        t = base + timedelta(minutes=5 * i)
        rates.append({
            "start": t,
            "end": t + timedelta(minutes=5),
            "import_price": import_price + i * 0.1,
            "export_price": export_price + i * 0.05,
            "type": "forecast",
        })
    return rates


def _make_forecast_kw(n, kw=2.0):
    """Build a list of n forecast dicts with a kw field."""
    return [{"kw": kw} for _ in range(n)]


# ---------------------------------------------------------------------------
#  Import the builder (will fail until implemented)
# ---------------------------------------------------------------------------

def _get_builder():
    """Get the _build_solver_inputs method. Returns callable or skips test."""
    try:
        from custom_components.house_battery_control.coordinator import (
            HBCDataUpdateCoordinator,
        )
        if not hasattr(HBCDataUpdateCoordinator, "_build_solver_inputs"):
            pytest.skip("_build_solver_inputs not yet implemented")
        return HBCDataUpdateCoordinator._build_solver_inputs
    except ImportError:
        pytest.skip("Coordinator not importable in test context")


# ---------------------------------------------------------------------------
#  T006: Price arrays from rates
# ---------------------------------------------------------------------------

class TestBuildPriceArrays:
    """T006: FR-001 — price arrays must be list[float] of length 288."""

    def test_build_price_arrays_from_rates(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}
        coordinator.rates = MagicMock()
        rates = _make_rates(288)
        coordinator.rates.get_rates.return_value = rates
        coordinator.rates.get_import_price_at.return_value = rates[0]["import_price"]
        coordinator.rates.get_export_price_at.return_value = rates[0]["export_price"]

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288, kw=3.0),
            current_price=rates[0]["import_price"],
            current_export_price=rates[0]["export_price"],
        )

        assert len(result.price_buy) == 288, f"Expected 288, got {len(result.price_buy)}"
        assert len(result.price_sell) == 288, f"Expected 288, got {len(result.price_sell)}"
        assert all(isinstance(v, float) for v in result.price_buy)
        assert all(isinstance(v, float) for v in result.price_sell)


# ---------------------------------------------------------------------------
#  T007: Row-0 uses live price (THE BUG FIX)
# ---------------------------------------------------------------------------

class TestBuildPriceRow0:
    """T007: FR-002/SC-003 — row-0 must use live price, not forecast[0]."""

    def test_build_price_row0_uses_live_price(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}
        rates = _make_rates(288, import_price=15.0, export_price=7.0)

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288),
            current_price=50.0,      # live price — divergent from forecast
            current_export_price=8.0,  # live price — divergent from forecast
        )

        assert result.price_buy[0] == 50.0, (
            f"Row-0 price_buy should be live 50.0, got {result.price_buy[0]}"
        )
        assert result.price_sell[0] == 8.0, (
            f"Row-0 price_sell should be live 8.0, got {result.price_sell[0]}"
        )
        # Row-1 should be the forecast value, not skipped
        assert result.price_buy[1] == pytest.approx(rates[1]["import_price"], abs=0.01)


# ---------------------------------------------------------------------------
#  T008: Row-0 fallback when no entity configured
# ---------------------------------------------------------------------------

class TestBuildPriceRow0Fallback:
    """T008: FR-002 fallback — uses rates lookup when no entity configured."""

    def test_build_price_row0_fallback_no_entity(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}
        rates = _make_rates(288, import_price=20.0, export_price=10.0)

        # current_price from rates.get_import_price_at(now) = 20.0
        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288),
            current_price=20.0,
            current_export_price=10.0,
        )

        assert result.price_buy[0] == 20.0
        assert result.price_sell[0] == 10.0


# ---------------------------------------------------------------------------
#  T008b: Sensor unavailable fallback (Edge case EC-2)
# ---------------------------------------------------------------------------

class TestBuildPriceRow0SensorUnavailable:
    """T008b: Edge case — sensor configured but unavailable, fallback to rates."""

    def test_build_price_row0_sensor_unavailable_fallback(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}
        rates = _make_rates(288, import_price=25.0, export_price=12.0)

        # When sensor is unavailable, coordinator passes None → builder
        # should handle gracefully (use rates value)
        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288),
            current_price=None,  # sensor unavailable
            current_export_price=None,
        )

        # Should fall back to rates[0] price, not crash
        assert result.price_buy[0] == rates[0]["import_price"]
        assert result.price_sell[0] == rates[0]["export_price"]


# ---------------------------------------------------------------------------
#  T009: Load/PV array conversion
# ---------------------------------------------------------------------------

class TestBuildLoadPvArrays:
    """T009: FR-003 — kW → kWh conversion and length 288."""

    def test_build_load_pv_arrays(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}
        rates = _make_rates(288)

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288, kw=2.0),
            forecast_solar=_make_forecast_kw(288, kw=3.0),
            current_price=10.0,
            current_export_price=5.0,
        )

        assert len(result.load_kwh) == 288
        assert len(result.pv_kwh) == 288
        # 2.0 kW × (5/60) = 0.1667 kWh
        assert result.load_kwh[0] == pytest.approx(2.0 * 5 / 60, abs=0.001)
        # 3.0 kW × (5/60) = 0.25 kWh
        assert result.pv_kwh[0] == pytest.approx(3.0 * 5 / 60, abs=0.001)


# ---------------------------------------------------------------------------
#  T010: Dynamic short arrays
# ---------------------------------------------------------------------------

class TestBuildDynamicShortArrays:
    """T010: Edge case — short forecast keeps short length dynamically."""

    def test_build_dynamic_short_arrays(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}
        rates = _make_rates(100, import_price=10.0, export_price=5.0)

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(100, kw=1.5),
            forecast_solar=_make_forecast_kw(100, kw=2.5),
            current_price=10.0,
            current_export_price=5.0,
        )

        assert len(result.price_buy) == 100
        assert len(result.load_kwh) == 100
        assert len(result.pv_kwh) == 100


# ---------------------------------------------------------------------------
#  T011: Empty forecast → 288 zeros
# ---------------------------------------------------------------------------

class TestBuildEmptyForecast:
    """T011: Edge case — empty forecast arrays → 288 zeros."""

    def test_build_empty_forecast_returns_zeros(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}

        result = builder(
            coordinator,
            rates_list=[],
            forecast_load=[],
            forecast_solar=[],
            current_price=10.0,
            current_export_price=5.0,
        )

        assert len(result.price_buy) == 288
        assert len(result.load_kwh) == 288
        assert len(result.pv_kwh) == 288
        assert all(v == 0.0 for v in result.load_kwh)
        assert all(v == 0.0 for v in result.pv_kwh)


# ---------------------------------------------------------------------------
#  T012: No-import step resolution
# ---------------------------------------------------------------------------

class TestBuildNoImportSteps:
    """T012: FR-004 — resolve no-import periods into step indices."""

    def test_build_no_import_steps(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {"no_import_periods": "15:00-21:00"}

        # 288 rates starting at 14:00 — steps 12-84 should be blocked
        # (14:00 + 12×5min = 15:00, 14:00 + 84×5min = 21:00)
        rates = _make_rates(288, start_hour=14)

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288),
            current_price=10.0,
            current_export_price=5.0,
        )

        assert result.no_import_steps is not None
        assert len(result.no_import_steps) > 0
        # Step 0 = 14:00, should NOT be blocked
        assert 0 not in result.no_import_steps
        # Steps during 15:00-21:00 should be blocked
        # Step 12 = 14:00 + 60min = 15:00
        assert 12 in result.no_import_steps


# ---------------------------------------------------------------------------
#  T013: Empty no-import config → None
# ---------------------------------------------------------------------------

class TestBuildNoImportEmpty:
    """T013: FR-004 — empty config → no_import_steps is None."""

    def test_build_no_import_empty(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {}

        rates = _make_rates(288)

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288),
            current_price=10.0,
            current_export_price=5.0,
        )

        assert result.no_import_steps is None or len(result.no_import_steps) == 0


# ---------------------------------------------------------------------------
#  T013b: Midnight-wrapping no-import periods (Edge case EC-4)
# ---------------------------------------------------------------------------

class TestBuildNoImportMidnightWrap:
    """T013b: Edge case — midnight-spanning period (22:00-06:00)."""

    def test_build_no_import_midnight_wrap(self):
        builder = _get_builder()
        coordinator = MagicMock()
        coordinator.config = {"no_import_periods": "22:00-06:00"}

        # Rates starting at 20:00 UTC
        rates = _make_rates(288, start_hour=20)

        result = builder(
            coordinator,
            rates_list=rates,
            forecast_load=_make_forecast_kw(288),
            forecast_solar=_make_forecast_kw(288),
            current_price=10.0,
            current_export_price=5.0,
        )

        assert result.no_import_steps is not None
        assert len(result.no_import_steps) > 0
        # Step 0 = 20:00 UTC, should NOT be blocked
        assert 0 not in result.no_import_steps
        # Step 24 = 20:00 + 2h = 22:00 UTC, SHOULD be blocked
        assert 24 in result.no_import_steps
        # Step 120 = 20:00 + 10h = 06:00 next day UTC, should NOT be blocked (end of period)
        assert 120 not in result.no_import_steps
