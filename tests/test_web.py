"""Tests for the Web Dashboard (web.py).

Tests written FIRST per @speckit.implement TDD.
Spec 2.2: Plan table columns.
Spec 2.3: Authentication flags.
Spec 3.1: Separate import/export rates in plan table.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant fixture."""
    return MagicMock(spec=HomeAssistant)

# --- Plan Table Requirements (from system_requirements.md 2.2) ---

REQUIRED_PLAN_COLUMNS = [
    "Time",
    "Local Time",
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

@pytest.mark.asyncio
async def test_config_yaml_handles_mappingproxytype():
    """config-yaml endpoint must handle MappingProxyType without throwing an error (fixes 500)."""
    from types import MappingProxyType
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCConfigYamlView

    view = HBCConfigYamlView()

    mock_request = MagicMock()
    mock_hass = MagicMock()
    mock_hass.data = {
        DOMAIN: {
            "entry_1": {
                "config": MappingProxyType({"foo": "bar", "capacity": 27.0})
            }
        }
    }
    mock_request.app = {"hass": mock_hass}

    response = await view.get(mock_request)
    assert response.content_type == "text/yaml"
    assert "foo: bar" in response.text


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


def test_load_history_api_public():
    """Load history API must be public."""
    from custom_components.house_battery_control.web import HBCLoadHistoryView
    assert HBCLoadHistoryView.requires_auth is False


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


def _build_test_table(data):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    coord = HBCDataUpdateCoordinator.__new__(HBCDataUpdateCoordinator)
    coord.fsm = MagicMock()
    coord.fsm.calculate_next_state.return_value = SimpleNamespace(
        state=data.get("state", "IDLE"),
        limit_kw=0.0,
        reason="Test"
    )
    coord.capacity_kwh = data.get("capacity", 27.0)
    coord.inverter_limit_kw = data.get("inverter_limit", 10.0)

    return coord._build_diagnostic_plan_table(
        rates=data.get("rates", []),
        solar_forecast=data.get("solar_forecast", []),
        load_forecast=data.get("load_forecast", []),
        weather=data.get("weather", []),
        current_soc=data.get("soc", 50.0),
        current_state=data.get("state", "IDLE")
    )


def test_plan_table_has_required_columns():
    """Plan table generator must include all system-required columns."""

    table = _build_test_table(_make_plan_data())

    assert isinstance(table, list)
    assert len(table) >= 1

    row = table[0]
    for col in REQUIRED_PLAN_COLUMNS:
        assert col in row, f"Missing column: {col}"


def test_plan_table_uses_actual_export_rate():
    """Plan table must use actual export rate from data, not hardcoded (spec 3.1)."""

    table = _build_test_table(_make_plan_data())
    row = table[0]
    assert row["Export Rate"] == "8.00", \
        f"Export Rate should be 8.00 from data, got {row['Export Rate']}"


def test_plan_table_time_format():
    """Time column should be HH:MM format."""
    import re

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

    table = _build_test_table(data)
    assert re.match(r"\d{2}:\d{2}", table[0]["Time"])
    assert re.match(r"\d{2}:\d{2}", table[0]["Local Time"])


def test_plan_table_interpolates_mixed_intervals():
    """Plan table must interpolate solcast, average load, and map weather strictly by UTC timestamp."""
    import datetime as dt

    start_time = dt.datetime(2025, 6, 15, 12, 0, tzinfo=dt.timezone.utc)

    # 1st row: 5 min. 2nd row: 30 min.
    rates = [
        {"start": start_time, "end": start_time + dt.timedelta(minutes=5), "price": 10.0},
        {"start": start_time + dt.timedelta(minutes=5), "end": start_time + dt.timedelta(minutes=35), "price": 12.0}
    ]

    # PV: Hourly block "12:00" = 6.0 kW total.
    solar_forecast = [
        {"period_start": start_time.isoformat(), "pv_estimate": 3.0}, # First 30 mins
        {"period_start": (start_time + dt.timedelta(minutes=30)).isoformat(), "pv_estimate": 3.0} # Second 30 mins
    ]

    # Load: 5 min blocks
    load_forecast = [
        {"start": start_time.isoformat(), "kw": 1.0}, # 12:00 - 12:05
        {"start": (start_time + dt.timedelta(minutes=5)).isoformat(), "kw": 2.0}, # 12:05 - 12:10
        {"start": (start_time + dt.timedelta(minutes=10)).isoformat(), "kw": 4.0}, # 12:10 - 12:15
        # Avg for the 30-min row (assuming these 2 match inside it, others missing/0) = 3.0
    ]

    # Weather
    weather = [
        {"datetime": start_time - dt.timedelta(minutes=10), "temperature": 15.0}, # Closest to 12:00 row
        {"datetime": start_time + dt.timedelta(minutes=40), "temperature": 20.0}  # Closest to 12:05 (30min) row? Diff to 12:05 is 35min. Diff from 15.0 to 12:05 is 15min. So 15.0 should win!
    ]

    data = _make_plan_data(
        rates=rates,
        solar_forecast=solar_forecast,
        load_forecast=load_forecast,
        weather=weather
    )

    table = _build_test_table(data)
    row_5m = table[0]
    row_30m = table[1]

    # 1. Weather: Nearest neighbor to 12:00 is 11:50 (15.0).
    assert row_5m["Air Temp Forecast"] == "15.0°C"
    # Nearest neighbor to 12:05 is 11:50 (15 min difference) vs 12:40 (35 min difference).
    assert row_30m["Air Temp Forecast"] == "15.0°C"

    # 2. PV Interpolation: Each 30-min block is exactly 3.0 kW.
    # 5 min row (12:00-12:05) matches the first block. pv_kw = 3.0. Energy output = 3.0 * (5/60) = 0.25 kWh
    # 30 min row (12:05-12:35) bridges block 1 & 2. pv_kw = 3.0. Energy output = 3.0 * (30/60) = 1.50 kWh
    assert row_5m["PV Forecast"] == "0.25"
    assert row_30m["PV Forecast"] == "1.50"

    # 3. Load average
    # 5 min row (12:00-12:05) matches only the first load block (1.0). Total avg = 1.0
    assert row_5m["Load Forecast"] == "1.00"
    # 30 min row (12:05-12:35) matches the next two load blocks (2.0 and 4.0). Avg = 3.0
    assert row_30m["Load Forecast"] == "3.00"


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


def test_plan_html_includes_local_time_column():
    """The /hbc/plan HTML view must render a 'Local Time' column header and cell data (Phase 14)."""
    from custom_components.house_battery_control.web import HBCPlanView

    view = HBCPlanView()

    # The view iterates over a hardcoded column list to build HTML.
    # Verify that "Local Time" is present in both the headers and row generators.
    # We inspect the source code by calling the internal column list.
    import inspect
    source = inspect.getsource(view.get)

    assert '"Local Time"' in source, \
        "HBCPlanView.get() must include 'Local Time' in its column list"


@pytest.mark.asyncio
async def test_load_history_api_returns_data(mock_hass):
    """Verify HBCLoadHistoryView returns both raw and derived data."""
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCLoadHistoryView

    view = HBCLoadHistoryView()

    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}

    # Mock coordinator with load_predictor
    mock_predictor = MagicMock()
    mock_predictor.last_history = [{"state": "10.0"}]
    mock_predictor.last_history_derived = [{"kw": 1.2}]

    mock_hass.data = {
        DOMAIN: {
            "entry_1": {
                "coordinator": MagicMock(load_predictor=mock_predictor)
            }
        }
    }

    response = await view.get(mock_request)
    import json
    data = json.loads(response.text)

    assert "raw_states" in data
    assert "derived_forecast" in data
    assert data["raw_states"][0]["state"] == "10.0"
    assert data["derived_forecast"][0]["kw"] == 1.2
