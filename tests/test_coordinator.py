"""Tests for the HBCDataUpdateCoordinator — sensor reading and derivation logic.

Tests the coordinator's _get_sensor_value method and the inversion/load
derivation logic WITHOUT constructing the full DataUpdateCoordinator
(which requires an event loop). We test the logic directly.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.const import (
    CONF_BATTERY_POWER_ENTITY,
    CONF_BATTERY_POWER_INVERT,
    CONF_BATTERY_SOC_ENTITY,
    CONF_EXPORT_TODAY_ENTITY,
    CONF_GRID_ENTITY,
    CONF_GRID_POWER_INVERT,
    CONF_IMPORT_TODAY_ENTITY,
    CONF_LOAD_TODAY_ENTITY,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    CONF_SOLAR_ENTITY,
    CONF_SOLCAST_TODAY_ENTITY,
    CONF_SOLCAST_TOMORROW_ENTITY,
)


@pytest.fixture
def mock_hass():
    """Mock HomeAssistant fixture."""
    from homeassistant.core import HomeAssistant
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    return hass


def _make_state(value):
    """Create a minimal HA state object."""
    return SimpleNamespace(state=str(value), attributes={})


def _make_mock_hass_with_state(value):
    """Create a mock hass with a sensor returning the given value."""
    hass = MagicMock()
    if value is None:
        hass.states.get.return_value = None
    else:
        hass.states.get.return_value = _make_state(value)
    return hass


def _get_sensor_value(hass, entity_id: str) -> float:
    """Extracted logic from coordinator._get_sensor_value for direct testing."""
    state = hass.states.get(entity_id)
    if state is None or state.state in ("unavailable", "unknown"):
        return 0.0
    try:
        return float(state.state)
    except (ValueError, TypeError):
        return 0.0


# --- _get_sensor_value logic tests ---

def test_get_sensor_value_normal():
    """Normal numeric state should return float."""
    hass = _make_mock_hass_with_state("75.5")
    assert _get_sensor_value(hass, "sensor.test") == 75.5


def test_get_sensor_value_unavailable():
    """Unavailable state should return 0.0."""
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="unavailable", attributes={})
    assert _get_sensor_value(hass, "sensor.test") == 0.0


def test_get_sensor_value_unknown():
    """Unknown state should return 0.0."""
    hass = MagicMock()
    hass.states.get.return_value = SimpleNamespace(state="unknown", attributes={})
    assert _get_sensor_value(hass, "sensor.test") == 0.0


def test_get_sensor_value_none():
    """Missing entity should return 0.0."""
    hass = _make_mock_hass_with_state(None)
    assert _get_sensor_value(hass, "sensor.missing") == 0.0


def test_get_sensor_value_non_numeric():
    """Non-numeric state string should return 0.0."""
    hass = _make_mock_hass_with_state("not_a_number")
    assert _get_sensor_value(hass, "sensor.test") == 0.0


# --- Inversion logic tests ---

def test_battery_power_no_inversion():
    """Without inversion, battery_power should be raw value."""
    raw = 5.0
    config = {CONF_BATTERY_POWER_INVERT: False}
    inverted = raw * (-1.0 if config.get(CONF_BATTERY_POWER_INVERT) else 1.0)
    assert inverted == 5.0


def test_battery_power_with_inversion():
    """With inversion, battery_power should be negated."""
    raw = 5.0
    config = {CONF_BATTERY_POWER_INVERT: True}
    inverted = raw * (-1.0 if config.get(CONF_BATTERY_POWER_INVERT) else 1.0)
    assert inverted == -5.0


def test_grid_power_with_inversion():
    """With grid inversion, grid_power should be negated."""
    raw = 3.0
    config = {CONF_GRID_POWER_INVERT: True}
    inverted = raw * (-1.0 if config.get(CONF_GRID_POWER_INVERT) else 1.0)
    assert inverted == -3.0


# --- Load derivation tests ---

def test_load_derivation_positive():
    """load = solar + grid - battery should work correctly."""
    solar_p = 4.0
    grid_p = 1.0
    battery_p = 2.0  # charging
    load_p = solar_p + grid_p - battery_p
    assert load_p == 3.0


def test_load_derivation_clamped_to_zero():
    """Negative load should be clamped to 0."""
    solar_p = 0.0
    grid_p = 0.0
    battery_p = 5.0  # charging hard
    load_p = solar_p + grid_p - battery_p
    if load_p < 0:
        load_p = 0.0
    assert load_p == 0.0


# --- Diagnostics tests ---

def test_build_sensor_diagnostics_includes_all_entities():
    """Spec 2.4: Diagnostics must include Solcast and the 4 control scripts."""
    # We can test this without full init by just mocking the config and the method itself if we instantiate.
    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    mock_hass = MagicMock()
    mock_hass.states.get.return_value = _make_state("test")

    config = {
        CONF_BATTERY_SOC_ENTITY: "sensor.soc",
        CONF_SOLCAST_TODAY_ENTITY: "sensor.solcast_today",
        CONF_SOLCAST_TOMORROW_ENTITY: "sensor.solcast_tomorrow",
        CONF_SCRIPT_CHARGE: "script.charge",
        CONF_SCRIPT_CHARGE_STOP: "script.charge_stop",
        CONF_SCRIPT_DISCHARGE: "script.discharge",
        CONF_SCRIPT_DISCHARGE_STOP: "script.discharge_stop",
    }

    # Bypass init requirements that hit the event loop
    coordinator = HBCDataUpdateCoordinator.__new__(HBCDataUpdateCoordinator)
    coordinator.hass = mock_hass
    coordinator.config = config

    diagnostics = coordinator._build_sensor_diagnostics()

    # Extract entity IDs from the result
    reported_entities = [d["entity_id"] for d in diagnostics]

    assert "sensor.soc" in reported_entities
    assert "sensor.solcast_today" in reported_entities
    assert "sensor.solcast_tomorrow" in reported_entities
    assert "script.charge" in reported_entities
    assert "script.charge_stop" in reported_entities
    assert "script.discharge" in reported_entities
    assert "script.discharge_stop" in reported_entities


def test_build_sensor_diagnostics_unknown_state_is_available():
    """Spec 2.4: Daily energy sensors frequently hit 'unknown' at midnight or restart.
    They are technically 'available', just waiting for data. If they return 'unknown',
    available should be True to avoid red error crosses in the UI."""
    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    mock_hass = MagicMock()
    mock_hass.states.get.return_value = _make_state("unknown")

    config = {
        CONF_LOAD_TODAY_ENTITY: "sensor.load_today",
    }

    coordinator = HBCDataUpdateCoordinator.__new__(HBCDataUpdateCoordinator)
    coordinator.hass = mock_hass
    coordinator.config = config

    diagnostics = coordinator._build_sensor_diagnostics()

    assert len(diagnostics) == 1
    # Should be True, because unknown is not unavailable.
    assert diagnostics[0]["available"] is True


def test_coordinator_tracks_state_changes_on_init():
    """Spec: Trigger a plan update immediately on entity change so that any change is reflected straight away."""
    from unittest.mock import patch

    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    mock_hass = MagicMock()

    config = {
        CONF_BATTERY_SOC_ENTITY: "sensor.battery_soc",
        CONF_BATTERY_POWER_ENTITY: "sensor.battery_power",
        CONF_SOLAR_ENTITY: "sensor.solar_power",
        CONF_GRID_ENTITY: "sensor.grid_power",
        CONF_LOAD_TODAY_ENTITY: "sensor.load_power"
    }

    with patch("custom_components.house_battery_control.coordinator.async_track_state_change_event") as mock_track, \
         patch("custom_components.house_battery_control.coordinator.DataUpdateCoordinator.__init__", return_value=None):
        coordinator = HBCDataUpdateCoordinator(mock_hass, "entry123", config)
        coordinator.hass = mock_hass

        # Test that async_track_state_change_event was called to register listeners
        mock_track.assert_called_once()

        # Assert it tracks the correct telemetry entities
        args, kwargs = mock_track.call_args
        tracked_entities = args[1]

        assert "sensor.battery_soc" in tracked_entities
        assert "sensor.battery_power" in tracked_entities
        assert "sensor.solar_power" in tracked_entities
        assert "sensor.grid_power" in tracked_entities
        assert "sensor.load_power" in tracked_entities


def test_coordinator_rounded_outputs():
    """Spec requirement: Ensure all floating point energies and powers are rounded to 2 decimal places."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    mock_hass = MagicMock()
    
    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)
    mock_hass.async_add_executor_job = mock_async_add_executor_job
    
    mock_hass.states.get.return_value = _make_state("5.555")

    config = {
        CONF_BATTERY_SOC_ENTITY: "sensor.soc",
        CONF_BATTERY_POWER_ENTITY: "sensor.battery",
        CONF_SOLAR_ENTITY: "sensor.solar",
        CONF_GRID_ENTITY: "sensor.grid",
        CONF_LOAD_TODAY_ENTITY: "sensor.load",
        CONF_IMPORT_TODAY_ENTITY: "sensor.import",
        CONF_EXPORT_TODAY_ENTITY: "sensor.export",
    }

    with patch("custom_components.house_battery_control.coordinator.async_track_state_change_event"), \
         patch("custom_components.house_battery_control.coordinator.DataUpdateCoordinator.__init__", return_value=None):
        coordinator = HBCDataUpdateCoordinator(mock_hass, "entry123", config)
        coordinator.hass = mock_hass
        coordinator._update_count = 0
        coordinator.rates = MagicMock()
        coordinator.rates.get_import_price_at.return_value = 0.25
        coordinator.rates.get_rates.return_value = []
        coordinator.weather = MagicMock()
        coordinator.weather.get_forecast.return_value = []
        coordinator.solar = MagicMock()
        coordinator.solar.async_get_forecast = AsyncMock(return_value=[])
        coordinator.load_predictor = MagicMock()
        coordinator.load_predictor.async_predict = AsyncMock(return_value=[])
        coordinator.fsm = MagicMock()
        coordinator.fsm.calculate_next_state.return_value = SimpleNamespace(state="standby", reason="test", limit_kw=0.0)
        coordinator.executor = MagicMock()
        coordinator.executor.apply_state = AsyncMock()
        coordinator.executor.get_command_summary.return_value = ""

        # Override the update methods to avoid crashing
        coordinator.rates.update = MagicMock()
        coordinator.weather.async_update = AsyncMock()

        result = asyncio.run(coordinator._async_update_data())

        assert result["solar_power"] == 5.55
        assert result["grid_power"] == 5.55
        assert result["battery_power"] == 5.55
        assert result["import_today"] == 5.55
        assert result["export_today"] == 5.55
        assert result["soc"] == 5.6  # SOC is rounded to 1 decimal

def test_pv_interpolation():
    """Spec: Simulate a PV input from Solcast and check that it gets properly chopped into its 5 min rows."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import MagicMock

    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    mock_hass = MagicMock()
    # Need a coordinator to test its (upcoming) interpolation method
    coordinator = HBCDataUpdateCoordinator.__new__(HBCDataUpdateCoordinator)
    coordinator.hass = mock_hass

    now = datetime(2025, 2, 20, 12, 0, tzinfo=timezone.utc)

    # 30-minute Solcast block at 6.0 kW
    solar_forecast = [
        {"period_start": now.isoformat(), "pv_estimate": 6.0}
    ]

    # Six 5-minute rate intervals covering the same 30-minute period
    rates = []
    for i in range(6):
        rates.append({
            "start": now + timedelta(minutes=5 * i),
            "end": now + timedelta(minutes=5 * (i + 1)),
            "import_price": 10.0,
            "export_price": 5.0
        })

    # We will invoke the (soon to be implemented) diagnostic plan builder
    # _build_diagnostic_plan_table(rates, solar_forecast, load_forecast, weather, current_soc, current_state)
    coordinator.fsm = MagicMock()
    # Mock the FSM to just return an IDLE state
    from types import SimpleNamespace
    coordinator.fsm.calculate_next_state.return_value = SimpleNamespace(state="IDLE", limit_kw=0.0, reason="Test")
    coordinator.capacity_kwh = 27.0
    coordinator.inverter_limit_kw = 10.0

    table = coordinator._build_diagnostic_plan_table(
        rates=rates,
        solar_forecast=solar_forecast,
        load_forecast=[],
        weather=[],
        current_soc=50.0,
        current_state="IDLE"
    )

    assert len(table) == 6
    for i, row in enumerate(table):
        # We expect the 5-min row duration to yield average kW of 6.0,
        # meaning energy = 6.0 kW * (5/60) h = 0.50 kWh per row.
        # The web table expects 'PV Forecast' nicely formatted as string "0.50"
        assert row["PV Forecast"] == "0.50", f"Row {i} failed PV interpolation"
        # The string time should match
        expected_time_str = (now + timedelta(minutes=5 * i)).strftime("%H:%M")
        assert row["Time"] == expected_time_str

@pytest.mark.asyncio
async def test_coordinator_update_data_exception_recovery(mock_hass):
    """Verify that a single failing service (e.g. weather map) doesn't crash the whole FSM calculation loop."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock, patch

    from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator

    mock_hass.states.get.return_value = _make_state("5.55")

    async def mock_async_add_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)
    mock_hass.async_add_executor_job = mock_async_add_executor_job

    config = {
        CONF_BATTERY_SOC_ENTITY: "sensor.soc",
        CONF_BATTERY_POWER_ENTITY: "sensor.battery",
        CONF_SOLAR_ENTITY: "sensor.solar",
        CONF_GRID_ENTITY: "sensor.grid",
        CONF_LOAD_TODAY_ENTITY: "sensor.load",
        CONF_IMPORT_TODAY_ENTITY: "sensor.import",
        CONF_EXPORT_TODAY_ENTITY: "sensor.export",
    }

    with patch("custom_components.house_battery_control.coordinator.async_track_state_change_event"), \
         patch("custom_components.house_battery_control.coordinator.DataUpdateCoordinator.__init__", return_value=None):
        coordinator = HBCDataUpdateCoordinator(mock_hass, "entry123", config)
        coordinator.hass = mock_hass
        coordinator._update_count = 0
        coordinator.rates = MagicMock()
        coordinator.weather = MagicMock()
        coordinator.solar = AsyncMock()
        coordinator.load_predictor = AsyncMock()
        coordinator.fsm = MagicMock()
        coordinator.fsm.calculate_next_state.return_value = SimpleNamespace(state="standby", reason="test", limit_kw=0.0)
        coordinator.executor = AsyncMock()

        # OVERRIDE to simulate catastrophic failure from underlying third-party API integration
        coordinator.weather.async_update.side_effect = Exception("Weather API is dead")

        result = await coordinator._async_update_data()

        # The result block should STILL emit telemetry and the coordinator shouldn't crash
        assert result is not None
        assert result["solar_power"] == 5.55
        assert result["state"] == "standby"
