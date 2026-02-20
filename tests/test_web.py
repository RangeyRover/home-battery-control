"""Tests for the Web Dashboard (web.py).

Tests written FIRST per @speckit.implement TDD.
Spec 2.2: Plan table columns.
Spec 2.3: Authentication flags.
Spec 3.1: Separate import/export rates in plan table.
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


# --- Auth Flags (Spec 2.3 — Custom Panel) ---
# All views are public; auth handled by HA frontend framework for the panel.

def test_dashboard_is_public():
    """Dashboard view must be public (spec 2.3 — panel handles auth)."""
    from custom_components.house_battery_control.web import HBCDashboardView
    assert HBCDashboardView.requires_auth is False


def test_plan_is_public():
    """Plan view must be public."""
    from custom_components.house_battery_control.web import HBCPlanView
    assert HBCPlanView.requires_auth is False


# --- YAML Config Endpoint (Spec 4.1) ---

def test_web_has_config_yaml_view():
    """web.py should have a YAML config export view (S2)."""
    import custom_components.house_battery_control.web as web
    assert hasattr(web, "HBCConfigYamlView"), "Missing HBCConfigYamlView for YAML export"


# --- Retroactive JS Data Structure Tests (S3) ---

def test_js_plan_data_structures():
    """Verify the data structures expected by the JS Plan tab are maintained (S3)."""
    # The JS expects:
    # rates: [{start: "toISOString", import_price: 10.0, export_price: 5.0}, ...]
    # solar_forecast: [{start: "toISOString", kw: 2.5}, ...]
    # We test the web.py build_status_data passthrough does not mangle these if they exist.
    from custom_components.house_battery_control.web import build_status_data

    # Mock coordinator output that satisfies JS expectations
    mock_data = {
        "rates": [
            {"start": "2026-02-19T13:30:00+00:00", "import_price": 25.0, "export_price": 8.0}
        ],
        "solar_forecast": [
            {"start": "2026-02-19T13:30:00+00:00", "kw": 3.4}
        ]
    }
    status = build_status_data(mock_data)

    # Assert JS requirements are preserved
    assert len(status["rates"]) == 1
    assert "start" in status["rates"][0]
    assert "import_price" in status["rates"][0]
    assert "export_price" in status["rates"][0]

    assert len(status["solar_forecast"]) == 1
    assert "start" in status["solar_forecast"][0]
    assert "kw" in status["solar_forecast"][0]


def test_api_status_is_public():
    """API status must be public (spec 2.3 — consumed by panel JS)."""
    from custom_components.house_battery_control.web import HBCApiStatusView
    assert HBCApiStatusView.requires_auth is False


def test_api_ping_public():
    """Ping endpoint must be public (spec 2.3)."""
    from custom_components.house_battery_control.web import HBCApiPingView
    assert HBCApiPingView.requires_auth is False


# --- Plan Table ---

def _make_plan_data(**overrides):
    """Helper: build minimal plan table input data."""
    base = {
        "soc": 50.0,
        "solar_power": 2.0,
        "load_power": 1.0,
        "rates": [
            {
                "start": datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc),
                "end": datetime(2025, 6, 15, 12, 5, tzinfo=timezone.utc),
                "import_price": 20.0,
                "export_price": 8.0,
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
    base.update(overrides)
    return base


def test_plan_table_has_required_columns():
    """Plan table generator must include all system-required columns."""
    from custom_components.house_battery_control.web import build_plan_table

    table = build_plan_table(_make_plan_data())

    assert isinstance(table, list)
    assert len(table) >= 1

    row = table[0]
    for col in REQUIRED_PLAN_COLUMNS:
        assert col in row, f"Missing column: {col}"


def test_plan_table_uses_actual_export_rate():
    """Plan table must use actual export rate from data, not hardcoded (spec 3.1)."""
    from custom_components.house_battery_control.web import build_plan_table

    table = build_plan_table(_make_plan_data())
    row = table[0]
    assert row["Export Rate"] == "8.0", \
        f"Export Rate should be 8.0 from data, got {row['Export Rate']}"


def test_plan_table_time_format():
    """Time column should be HH:MM format."""
    import re

    from custom_components.house_battery_control.web import build_plan_table

    data = _make_plan_data(
        rates=[{
            "start": datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc),
            "end": datetime(2025, 6, 15, 14, 35, tzinfo=timezone.utc),
            "import_price": 20.0,
            "export_price": 8.0,
            "type": "ACTUAL",
        }],
        solar_forecast=[
            {"start": datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc), "kw": 3.0}
        ],
    )

    table = build_plan_table(data)
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
    assert "Solar" in svg or "PV" in svg
    assert "Grid" in svg
    assert "Battery" in svg
    assert "House" in svg or "Load" in svg


# --- API Diagnostics (Spec 2.4 — Full Passthrough) ---

def test_build_status_data_passes_all_coordinator_keys():
    """build_status_data must pass through ALL coordinator data, not cherry-pick (spec 2.4)."""
    from custom_components.house_battery_control.web import build_status_data

    mock_data = {
        # Telemetry
        "soc": 75.0,
        "solar_power": 3.5,
        "grid_power": -1.0,
        "battery_power": 2.0,
        "load_power": 2.5,
        # Accumulators
        "load_today": 12.5,
        "import_today": 8.3,
        "export_today": 4.1,
        # Pricing
        "current_price": 25.5,
        "rates": [{"start": "2025-06-15T00:00:00+00:00", "import_price": 25.5, "export_price": 8.0}],
        # Forecasts
        "weather": [{"temperature": 22.0}],
        "solar_forecast": [{"kw": 3.0}],
        "load_forecast": [1.5, 1.6],
        # Constants
        "capacity": 27.0,
        "charge_rate_max": 6.3,
        "inverter_limit": 10.0,
        # FSM
        "state": "CHARGE_SOLAR",
        "reason": "Excess solar",
        "limit_kw": 5.0,
        "plan_html": "<p>Plan</p>",
        # Diagnostics
        "sensors": [
            {"entity_id": "sensor.soc", "state": "75.0", "available": True, "attributes": {"unit": "%"}},
        ],
        "last_update": "2025-06-15T12:00:00+00:00",
        "update_count": 42,
    }

    status = build_status_data(mock_data)

    # ALL coordinator keys must be present
    for key in mock_data:
        assert key in status, f"Missing key '{key}' in status output"
        assert status[key] == mock_data[key], f"Key '{key}' value mismatch"


def test_build_status_data_sensor_attributes():
    """Sensor diagnostics must include attributes dict (spec 2.4)."""
    from custom_components.house_battery_control.web import build_status_data

    mock_data = {
        "soc": 50.0,
        "state": "IDLE",
        "sensors": [
            {
                "entity_id": "sensor.battery_soc",
                "state": "50.0",
                "available": True,
                "attributes": {"unit_of_measurement": "%", "device_class": "battery"},
            },
        ],
    }
    status = build_status_data(mock_data)
    assert "attributes" in status["sensors"][0]
    assert status["sensors"][0]["attributes"]["unit_of_measurement"] == "%"


def test_build_status_data_empty_input():
    """build_status_data must not crash with empty dict (backward compat)."""
    from custom_components.house_battery_control.web import build_status_data

    status = build_status_data({})
    assert isinstance(status, dict)
    # Must at least have sensors default
    assert status.get("sensors", []) == []


