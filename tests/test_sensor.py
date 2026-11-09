"""Tests for the Sensor platform."""

from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.const import ATTR_PLAN_HTML
from custom_components.house_battery_control.sensor import (
    HBCReasonSensor,
    HBCStateSensor,
    HBCSyntheticRatesDiagnosticSensor,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with sample data."""
    coord = MagicMock()
    coord.entry_id = "test_entry_id"
    coord.data = {
        "state": "CHARGE_GRID",
        "reason": "Negative price detected",
        "plan_html": "<table><tr><td>Test</td></tr></table>",
    }
    return coord


def test_state_sensor_returns_state(mock_coordinator):
    """State sensor should return the FSM state from coordinator data."""
    sensor = HBCStateSensor(mock_coordinator)
    assert sensor.native_value == "CHARGE_GRID"


def test_state_sensor_defaults_to_idle(mock_coordinator):
    """State sensor should default to SELF_CONSUMPTION when no state in data."""
    mock_coordinator.data = {}
    sensor = HBCStateSensor(mock_coordinator)
    assert sensor.native_value == "SELF_CONSUMPTION"


def test_reason_sensor_returns_reason(mock_coordinator):
    """Reason sensor should return the reason string."""
    sensor = HBCReasonSensor(mock_coordinator)
    assert sensor.native_value == "Negative price detected"


def test_reason_sensor_defaults_to_initializing(mock_coordinator):
    """Reason sensor should default to 'Initializing...' when no reason."""
    mock_coordinator.data = {}
    sensor = HBCReasonSensor(mock_coordinator)
    assert sensor.native_value == "Initializing..."


def test_reason_sensor_extra_attributes(mock_coordinator):
    """Reason sensor should expose plan_html in extra state attributes."""
    sensor = HBCReasonSensor(mock_coordinator)
    attrs = sensor.extra_state_attributes
    assert ATTR_PLAN_HTML in attrs
    assert attrs[ATTR_PLAN_HTML] == "<table><tr><td>Test</td></tr></table>"


def test_reason_sensor_empty_plan_html(mock_coordinator):
    """Empty plan_html should still be present as empty string."""
    mock_coordinator.data = {"reason": "test", "plan_html": ""}
    sensor = HBCReasonSensor(mock_coordinator)
    assert sensor.extra_state_attributes[ATTR_PLAN_HTML] == ""




class TestHBCSyntheticRatesDiagnosticSensor:
    def test_sensor_returns_data(self, mock_coordinator):
        mock_coordinator.data = {"synthetic_analog_days": ["2025-01-01"], "synthetic_pricing_curve": [3.0]}
        sensor = HBCSyntheticRatesDiagnosticSensor(mock_coordinator)
        assert sensor.native_value == "Active"
        assert sensor.extra_state_attributes["analog_days"] == ["2025-01-01"]
        assert sensor.extra_state_attributes["pricing_curve"] == [3.0]

    def test_sensor_inactive_when_no_data(self, mock_coordinator):
        mock_coordinator.data = {}
        sensor = HBCSyntheticRatesDiagnosticSensor(mock_coordinator)
        assert sensor.native_value == "Inactive"
        assert sensor.extra_state_attributes.get("analog_days") is None




class TestHBCSolveTimeSensor:
    """T023/US4: Tests for HBCSolveTimeSensor."""

    def test_solve_time_sensor_returns_value_and_attributes(self, mock_coordinator):
        from custom_components.house_battery_control.sensor import HBCSolveTimeSensor
        from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
        from homeassistant.const import EntityCategory, UnitOfTime

        mock_coordinator.data = {
            "solver_stats": {
                "solve_seconds": 0.412,
                "budget_seconds": 30.0,
                "passes": 2,
                "integer_used": True,
                "reference_solve": True,
                "outcome": "optimal",
                "detail": "",
                "horizon_steps": 288,
            },
            "solve_seconds_max_24h": 1.234,
        }
        sensor = HBCSolveTimeSensor(mock_coordinator)
        assert sensor.unique_id == "test_entry_id_hbc_solve_time"
        assert sensor.native_value == 0.412
        assert sensor.device_class == SensorDeviceClass.DURATION
        assert sensor.native_unit_of_measurement == UnitOfTime.SECONDS
        assert sensor.state_class == SensorStateClass.MEASUREMENT
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC

        attrs = sensor.extra_state_attributes
        assert attrs["budget_seconds"] == 30.0
        assert attrs["passes"] == 2
        assert attrs["outcome"] == "optimal"
        assert attrs["solve_seconds_max_24h"] == 1.234

    def test_solve_time_sensor_none_when_missing(self, mock_coordinator):
        from custom_components.house_battery_control.sensor import HBCSolveTimeSensor

        mock_coordinator.data = {}
        sensor = HBCSolveTimeSensor(mock_coordinator)
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}
