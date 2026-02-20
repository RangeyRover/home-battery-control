"""Tests for the Web Dashboard (web.py).

Written BEFORE implementation per TDD discipline.
Tests validate route structure, plan table columns, API responses.
"""
from datetime import datetime, timezone

# --- Plan Table Requirements (from system_requirements.md 2.2) ---

REQUIRED_PLAN_COLUMNS = [
    "Time",
    "Import Rate",
    "Export Rate",
    "FSM State",
    "Inverter Limit",
    "PV Forecast",
    "Load Forecast",
    "Air Temp Forecast",
    "SoC Forecast",
    "Interval Cost",
    "Cumulative Total",
]


def test_web_module_importable():
    """web.py module should be importable."""
    from custom_components.house_battery_control.web import HBCDashboardView
    assert HBCDashboardView is not None


def test_web_has_plan_view():
    """web.py should have a plan view class."""
    from custom_components.house_battery_control.web import HBCPlanView
    assert HBCPlanView is not None


def test_web_has_api_status():
    """web.py should have a JSON API status view."""
    from custom_components.house_battery_control.web import HBCApiStatusView
    assert HBCApiStatusView is not None


def test_web_has_api_ping():
    """web.py should have a health-check ping view."""
    from custom_components.house_battery_control.web import HBCApiPingView
    assert HBCApiPingView is not None


# --- Plan Table ---

def test_plan_table_has_required_columns():
    """Plan table generator must include all system-required columns."""
    from custom_components.house_battery_control.web import build_plan_table

    # Minimal mock data
    mock_data = {
        "soc": 50.0,
        "solar_power": 2.0,
        "load_power": 1.0,
        "rates": [
            {
                "start": datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc),
                "end": datetime(2025, 6, 15, 12, 5, tzinfo=timezone.utc),
                "price": 20.0,
                "type": "ACTUAL",
            }
        ],
        "solar_forecast": [
            {"start": datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc), "kw": 3.0}
        ],
        "load_forecast": [0.5],
        "capacity": 27.0,
        "charge_rate_max": 6.3,
        "inverter_limit": 10.0,
        "state": "IDLE",
    }

    table = build_plan_table(mock_data)

    # Must be a list of dicts
    assert isinstance(table, list)
    assert len(table) >= 1

    # Each row must have all required keys
    row = table[0]
    for col in REQUIRED_PLAN_COLUMNS:
        assert col in row, f"Missing column: {col}"


def test_plan_table_time_format():
    """Time column should be HH:MM format."""
    from custom_components.house_battery_control.web import build_plan_table

    mock_data = {
        "soc": 50.0,
        "solar_power": 2.0,
        "load_power": 1.0,
        "rates": [
            {
                "start": datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc),
                "end": datetime(2025, 6, 15, 14, 35, tzinfo=timezone.utc),
                "price": 20.0,
                "type": "ACTUAL",
            }
        ],
        "solar_forecast": [
            {"start": datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc), "kw": 3.0}
        ],
        "load_forecast": [1.0],
        "capacity": 27.0,
        "charge_rate_max": 6.3,
        "inverter_limit": 10.0,
        "state": "IDLE",
    }

    table = build_plan_table(mock_data)
    # Time should match HH:MM pattern
    import re
    assert re.match(r"\d{2}:\d{2}", table[0]["Time"])


# --- API Status ---

def test_api_status_returns_dict():
    """Status API helper should return a dict with key fields."""
    from custom_components.house_battery_control.web import build_status_data

    mock_data = {
        "soc": 75.0,
        "solar_power": 3.5,
        "grid_power": -1.0,
        "battery_power": 2.0,
        "load_power": 2.5,
        "current_price": 25.5,
        "state": "CHARGE_SOLAR",
        "reason": "Excess solar",
    }

    status = build_status_data(mock_data)
    assert "soc" in status
    assert "state" in status
    assert "reason" in status
    assert status["soc"] == 75.0
    assert status["state"] == "CHARGE_SOLAR"


# --- Power Flow Diagram ---

def test_power_flow_svg():
    """Power flow diagram generator must return valid SVG string."""
    from custom_components.house_battery_control.web import build_power_flow_svg

    svg = build_power_flow_svg(
        solar_kw=3.5,
        grid_kw=-1.0,
        battery_kw=2.0,
        load_kw=2.5,
        soc=75.0,
    )
    assert isinstance(svg, str)
    assert "<svg" in svg
    assert "</svg>" in svg
    # Should contain the 4 nodes
    assert "Solar" in svg or "PV" in svg
    assert "Grid" in svg
    assert "Battery" in svg
    assert "House" in svg or "Load" in svg
