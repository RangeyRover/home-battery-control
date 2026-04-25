"""Tests for the Web Dashboard (web.py).

Tests written FIRST per @speckit.implement TDD.
Spec 2.2: Plan table columns.
Spec 2.3: Admin-only authentication.
Spec 3.1: Separate import/export rates in plan table.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.web import HBCSyntheticOutlookView
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
    "Net Grid",
    "PV Forecast",
    "Load Forecast",
    "Air Temp Forecast",
    "Temp Delta",
    "Load Adj.",
    "SoC Forecast",
    "Interval Cost",
    "Cumul. Cost",
    "Acq. Cost",
]


def test_web_module_importable():
    """web.py module should be importable."""
    from custom_components.house_battery_control.web import HBCDashboardView

    assert HBCDashboardView is not None


def test_web_has_api_status():
    """web.py should have a JSON API status view."""
    from custom_components.house_battery_control.web import HBCApiStatusView

    assert HBCApiStatusView is not None


def test_web_has_api_ping():
    """web.py should have a health-check ping view."""
    from custom_components.house_battery_control.web import HBCApiPingView

    assert HBCApiPingView is not None


# --- Auth Flags (Spec 2.3 — Admin-Only) ---
# All views require admin auth; HA frontend framework enforces for the panel.


def test_dashboard_requires_auth():
    """Dashboard view must require auth (FR-001)."""
    from custom_components.house_battery_control.web import HBCDashboardView

    assert HBCDashboardView.requires_auth is True


@pytest.mark.asyncio
async def test_dashboard_html_rendering_and_svg(mock_hass):
    """Verify HBCDashboardView renders full HTML and an embedded SVG graph."""
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCDashboardView

    view = HBCDashboardView()

    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}

    mock_coord = MagicMock()
    mock_coord.data = {
        "soc": 65.5,
        "solar_power": 4.1,
        "grid_power": -2.0,
        "load_power": 1.5,
        "current_price": 12.3,
        "state": "IDLE",
        "reason": "Stable operation",
    }

    mock_hass.data = {DOMAIN: {"entry_1": {"coordinator": mock_coord}}}

    response = await view.get(mock_request)

    assert response.status == 200
    assert response.content_type == "text/html"
    html = response.text

    # Assert structural HTML
    assert "<!DOCTYPE html>" in html
    assert "House Battery Control" in html

    # Assert SVG graph components
    assert "<svg" in html
    assert "House" in html
    assert "Battery" in html

    # Assert statistics formatting
    assert "66%" in html  # Rounded from 65.5
    assert "4.1" in html
    assert "1.5" in html
    assert "IDLE" in html


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
        DOMAIN: {"entry_1": {"config": MappingProxyType({"foo": "bar", "capacity": 27.0})}}
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
        "solar_forecast": [{"start": "2026-02-19T13:30:00+00:00", "kw": 3.4}],
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


def test_api_status_requires_auth():
    """API status must require auth (FR-001)."""
    from custom_components.house_battery_control.web import HBCApiStatusView

    assert HBCApiStatusView.requires_auth is True


def test_api_ping_requires_auth():
    """Ping endpoint must require auth (FR-001)."""
    from custom_components.house_battery_control.web import HBCApiPingView

    assert HBCApiPingView.requires_auth is True


def test_load_history_api_requires_auth():
    """Load history API must require auth (FR-001)."""
    from custom_components.house_battery_control.web import HBCLoadHistoryView

    assert HBCLoadHistoryView.requires_auth is True


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
        "solar_forecast": [{"start": datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc), "kw": 3.0}],
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
    coord.config = {}
    coord.fsm = MagicMock()
    coord.fsm.calculate_next_state.return_value = SimpleNamespace(
        state=data.get("state", "IDLE"), limit_kw=0.0, reason="Test"
    )
    coord.capacity_kwh = data.get("capacity", 27.0)
    coord.inverter_limit_kw = data.get("inverter_limit", 10.0)

    return coord._build_diagnostic_plan_table(
        rates=data.get("rates", []),
        solar_forecast=data.get("solar_forecast", []),
        load_forecast=data.get("load_forecast", []),
        weather=data.get("weather", []),
        current_soc=data.get("soc", 50.0),
        future_plan=data.get("future_plan", []),
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
    assert row["Export Rate"] == "8.00", (
        f"Export Rate should be 8.00 from data, got {row['Export Rate']}"
    )


def test_plan_table_time_format():
    """Time column should be HH:MM format."""
    import re

    data = _make_plan_data(
        rates=[
            {
                "start": datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc),
                "end": datetime(2025, 6, 15, 14, 35, tzinfo=timezone.utc),
                "import_price": 20.0,
                "export_price": 8.0,
                "type": "ACTUAL",
            }
        ],
        solar_forecast=[{"start": datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc), "kw": 3.0}],
    )

    table = _build_test_table(data)
    assert re.match(r"\d{2}:\d{2}", table[0]["Time"])
    assert re.match(r"\d{2}:\d{2}", table[0]["Local Time"])


def test_plan_table_extracts_rates_and_power_from_plan():
    """Plan table must seamlessly render the FSM array variables mapping directly to the row timeline."""
    import datetime as dt

    start_time = dt.datetime(2025, 6, 15, 12, 0, tzinfo=dt.timezone.utc)

    # 1st row: 5 min. 2nd row: 30 min.
    rates = [
        {"start": start_time, "end": start_time + dt.timedelta(minutes=5), "price": 10.0},
        {
            "start": start_time + dt.timedelta(minutes=5),
            "end": start_time + dt.timedelta(minutes=35),
            "price": 12.0,
        },
    ]

    # Weather
    weather = [
        {
            "datetime": start_time - dt.timedelta(minutes=10),
            "temperature": 15.0,
        },  # Closest to 12:00 row
        {
            "datetime": start_time + dt.timedelta(minutes=40),
            "temperature": 20.0,
        },  # Closest to 12:05 (30min) row? Diff to 12:05 is 35min. Diff from 15.0 to 12:05 is 15min. So 15.0 should win!
    ]

    # Because `future_plan` provides the kW values directly for each row interval.
    # We provide a mock sequence matching the rates length.
    future_plan = [
        {
            "target_soc": 50.0,
            "load": 1.0,
            "pv": 3.0,
            # We explicitly define export_price in future_plan as proof that the UI uses it mapping directly:
            "import_price": 10.0,
            "export_price": 5.0,
            "grid_import": 0.0,
            "state": "SELF_CONSUMPTION",
        },
        {
            "target_soc": 50.0,
            "load": 3.0,
            "pv": 3.0,
            "import_price": 12.0,
            "export_price": 8.0,
            "grid_import": 0.0,
            "state": "IDLE",
        },
    ]

    data = _make_plan_data(
        rates=rates, solar_forecast=[], load_forecast=[], weather=weather, future_plan=future_plan
    )

    table = _build_test_table(data)
    row_5m = table[0]
    row_30m = table[1]

    # 1. Weather: Nearest neighbor to 12:00 is 11:50 (15.0).
    assert row_5m["Air Temp Forecast"] == "15.0°C"
    # Nearest neighbor to 12:05 is 11:50 (15 min difference) vs 12:40 (35 min difference).
    assert row_30m["Air Temp Forecast"] == "15.0°C"

    # 2. Extract PV directly from future_plan
    assert row_5m["PV Forecast"] == "3.00"
    assert row_30m["PV Forecast"] == "3.00"

    # 3. Extract Load directly from future_plan
    assert row_5m["Load Forecast"] == "1.00"
    assert row_30m["Load Forecast"] == "3.00"

    # 4. Extract Rates directly from future_plan
    assert row_5m["Export Rate"] == "5.00"
    assert row_30m["Export Rate"] == "8.00"


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
        "rates": [
            {"start": "2025-06-15T00:00:00+00:00", "import_price": 25.5, "export_price": 8.0}
        ],
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
            {
                "entity_id": "sensor.soc",
                "state": "75.0",
                "available": True,
                "attributes": {"unit": "%"},
            },
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
    mock_predictor.last_history_raw = [[{"state": "10.0"}]]

    mock_hass.data = {
        DOMAIN: {"entry_1": {"coordinator": MagicMock(load_predictor=mock_predictor)}}
    }

    response = await view.get(mock_request)
    import json

    data = json.loads(response.text)

    # Asserts testing the REST-equivalent 2D array payload schema
    assert isinstance(data, list)
    assert isinstance(data[0], list)
    assert data[0][0]["state"] == "10.0"


# --- Synthetic Outlook API (Spec 037) ---



@pytest.mark.asyncio
async def test_synthetic_outlook_api_returns_data(mock_hass):
    """Verify HBCSyntheticOutlookView returns analog days and curve."""
    view = HBCSyntheticOutlookView()
    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}

    # Mock coordinator with rates predictor
    mock_coord = MagicMock()
    mock_coord.data = {
        "synthetic_analog_days": ["2025-01-01", "2025-01-02"],
        "synthetic_pricing_curve": [3.0, 4.0]
    }

    from custom_components.house_battery_control.const import DOMAIN
    mock_hass.data = {
        DOMAIN: {"entry_1": {"coordinator": mock_coord}}
    }

    response = await view.get(mock_request)
    import json
    data = json.loads(response.text)

    assert "synthetic_analog_days" in data
    assert "synthetic_pricing_curve" in data
    assert data["synthetic_analog_days"] == ["2025-01-01", "2025-01-02"]
    assert data["synthetic_pricing_curve"] == [3.0, 4.0]

# --- Telemetry API Split (Spec 050) ---

def test_web_has_api_telemetry():
    """web.py should have a telemetry JSON API view."""
    import custom_components.house_battery_control.web as web
    assert hasattr(web, "HBCApiTelemetryView"), "Missing HBCApiTelemetryView"

def test_web_has_api_plan():
    """web.py should have a plan JSON API view."""
    import custom_components.house_battery_control.web as web
    assert hasattr(web, "HBCApiPlanView"), "Missing HBCApiPlanView"

def test_web_has_api_outlook():
    """web.py should have an outlook JSON API view."""
    import custom_components.house_battery_control.web as web
    assert hasattr(web, "HBCApiOutlookView"), "Missing HBCApiOutlookView"

@pytest.mark.asyncio
async def test_api_telemetry_returns_core_data(mock_hass):
    """Verify HBCApiTelemetryView returns only core variables and excludes heavy arrays."""
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCApiTelemetryView

    view = HBCApiTelemetryView()
    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}

    mock_coord = MagicMock()
    mock_coord.data = {
        "soc": 65.5,
        "state": "IDLE",
        "reason": "Stable",
        "sensors": [{"heavy": "payload"}],  # Should be excluded
        "rates": [{"heavy": "payload"}],    # Should be excluded
    }

    # Needs a build_telemetry_payload method on the coordinator
    mock_coord._build_telemetry_payload = MagicMock(return_value={"soc": 65.5, "state": "IDLE", "reason": "Stable"})
    mock_hass.data = {DOMAIN: {"entry_1": {"coordinator": mock_coord}}}

    response = await view.get(mock_request)
    import json
    data = json.loads(response.text)

    assert "soc" in data
    assert "state" in data
    assert "sensors" not in data
    assert "rates" not in data

@pytest.mark.asyncio
async def test_api_plan_returns_columnar_matrix(mock_hass):
    """Verify HBCApiPlanView returns a columnar matrix (columns, rows)."""
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCApiPlanView

    view = HBCApiPlanView()
    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}
    # Mock default query params
    mock_request.query = {}

    mock_coord = MagicMock()
    # Mock the method that will build the matrix
    mock_coord._build_plan_matrix = MagicMock(return_value={
        "columns": ["Time", "FSM State"],
        "rows": [["12:00", "IDLE"]]
    })
    mock_hass.data = {DOMAIN: {"entry_1": {"coordinator": mock_coord}}}

    response = await view.get(mock_request)
    import json
    data = json.loads(response.text)

    assert "columns" in data
    assert "rows" in data
    assert "Time" in data["columns"]
    assert data["rows"][0][0] == "12:00"

@pytest.mark.asyncio
async def test_api_outlook_returns_transitions(mock_hass):
    """Verify HBCApiOutlookView returns only state_transitions."""
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCApiOutlookView

    view = HBCApiOutlookView()
    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}

    mock_coord = MagicMock()
    mock_coord.data = {
        "state_transitions": [{"heavy": "payload"}],
        "sensors": [{"heavy": "payload"}],  # Should be excluded
    }
    mock_hass.data = {DOMAIN: {"entry_1": {"coordinator": mock_coord}}}

    response = await view.get(mock_request)
    import json
    data = json.loads(response.text)

    assert "state_transitions" in data
    assert "sensors" not in data

@pytest.mark.asyncio
async def test_api_plan_passes_resolution(mock_hass):
    """Verify HBCApiPlanView passes resolution query parameter."""
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.const import DOMAIN
    from custom_components.house_battery_control.web import HBCApiPlanView

    view = HBCApiPlanView()
    mock_request = MagicMock()
    mock_request.app = {"hass": mock_hass}
    mock_request.query = {"resolution": "5min"}

    mock_coord = MagicMock()
    mock_coord._build_plan_matrix = MagicMock(return_value={"columns": [], "rows": []})
    mock_hass.data = {DOMAIN: {"entry_1": {"coordinator": mock_coord}}}

    await view.get(mock_request)
    mock_coord._build_plan_matrix.assert_called_once_with(resolution="5min")
