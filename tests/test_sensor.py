"""Tests for the Sensor platform."""

from unittest.mock import MagicMock

import pytest
from custom_components.house_battery_control.const import ATTR_PLAN_HTML
from custom_components.house_battery_control.sensor import (
    HBCReasonSensor,
    HBCStateSensor,
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


def test_limit_kw_sensor_returns_value(mock_coordinator):
    """HBCLimitKwSensor should return the limit_kw value from coordinator data."""
    from custom_components.house_battery_control.sensor import HBCLimitKwSensor

    mock_coordinator.data["limit_kw"] = 6.3
    sensor = HBCLimitKwSensor(mock_coordinator)
    assert sensor.native_value == 6.3


def test_limit_kw_sensor_returns_none_when_missing(mock_coordinator):
    """HBCLimitKwSensor should return None when limit_kw not in data."""
    from custom_components.house_battery_control.sensor import HBCLimitKwSensor

    mock_coordinator.data = {}
    sensor = HBCLimitKwSensor(mock_coordinator)
    assert sensor.native_value is None


def test_dp_target_soc_sensor_returns_value(mock_coordinator):
    """HBCDpTargetSocSensor should return the target_soc value from coordinator data."""
    from custom_components.house_battery_control.sensor import HBCDpTargetSocSensor

    mock_coordinator.data["target_soc"] = 85.0
    sensor = HBCDpTargetSocSensor(mock_coordinator)
    assert sensor.native_value == 85.0
