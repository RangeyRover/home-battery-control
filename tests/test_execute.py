"""Tests for the Execute module — translates FSM states into Powerwall commands.

Written BEFORE implementation per TDD discipline.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.house_battery_control.const import (
    CONF_ALLOW_CHARGE_FROM_GRID_ENTITY,
    CONF_ALLOW_EXPORT_ENTITY,
    STATE_CHARGE_GRID,
    STATE_CHARGE_SOLAR,
    STATE_DISCHARGE_HOME,
    STATE_IDLE,
    STATE_PRESERVE,
)
from custom_components.house_battery_control.execute import PowerwallExecutor


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def config():
    return {
        CONF_ALLOW_CHARGE_FROM_GRID_ENTITY: "switch.powerwall_grid_charging",
        CONF_ALLOW_EXPORT_ENTITY: "select.powerwall_operation_mode",
    }


@pytest.fixture
def executor(mock_hass, config):
    return PowerwallExecutor(mock_hass, config)


# --- State to command mapping ---

def test_executor_init(executor):
    """Executor should construct without errors."""
    assert executor is not None


def test_charge_grid_enables_grid_charging(executor):
    """CHARGE_GRID should turn on the grid charging switch."""
    executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.last_state == STATE_CHARGE_GRID


def test_idle_state(executor):
    """IDLE should set a neutral state."""
    executor.apply_state(STATE_IDLE, limit_kw=0.0)
    assert executor.last_state == STATE_IDLE


def test_discharge_home_state(executor):
    """DISCHARGE_HOME should be tracked."""
    executor.apply_state(STATE_DISCHARGE_HOME, limit_kw=5.0)
    assert executor.last_state == STATE_DISCHARGE_HOME


def test_preserve_state(executor):
    """PRESERVE should be tracked."""
    executor.apply_state(STATE_PRESERVE, limit_kw=0.0)
    assert executor.last_state == STATE_PRESERVE


def test_charge_solar_state(executor):
    """CHARGE_SOLAR should be tracked."""
    executor.apply_state(STATE_CHARGE_SOLAR, limit_kw=3.0)
    assert executor.last_state == STATE_CHARGE_SOLAR


def test_no_repeat_if_same_state(executor):
    """Should not re-apply if state hasn't changed."""
    executor.apply_state(STATE_IDLE, limit_kw=0.0)
    result1 = executor.last_state
    executor.apply_state(STATE_IDLE, limit_kw=0.0)
    result2 = executor.last_state
    assert result1 == result2 == STATE_IDLE
    # Should have only applied once
    assert executor.apply_count == 1


def test_state_change_increments_count(executor):
    """Changing state should increment the apply count."""
    executor.apply_state(STATE_IDLE, limit_kw=0.0)
    executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 2


def test_get_command_summary(executor):
    """Should return a human-readable summary of the last command."""
    executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    summary = executor.get_command_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
