"""Tests for the Execute module — translates FSM states into Powerwall commands.

Written BEFORE implementation per TDD discipline.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.house_battery_control.const import (
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    STATE_CHARGE_GRID,
    STATE_CHARGE_SOLAR,
    STATE_DISCHARGE_HOME,
    STATE_DISCHARGE_GRID,
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
        CONF_SCRIPT_CHARGE: "script.force_charge",
        CONF_SCRIPT_CHARGE_STOP: "script.charge_stop",
        CONF_SCRIPT_DISCHARGE: "script.force_discharge",
        CONF_SCRIPT_DISCHARGE_STOP: "script.discharge_stop",
    }


@pytest.fixture
def executor(mock_hass, config):
    return PowerwallExecutor(mock_hass, config)


# --- State to command mapping ---

def test_executor_init(executor):
    """Executor should construct without errors."""
    assert executor is not None


@pytest.mark.asyncio
async def test_charge_grid_calls_charge_script(executor, mock_hass):
    """CHARGE_GRID should call the charge script."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.last_state == STATE_CHARGE_GRID
    mock_hass.services.async_call.assert_called_with(
        "script", "turn_on", {"entity_id": "script.force_charge"}
    )


@pytest.mark.asyncio
async def test_idle_after_charge_calls_charge_stop(executor, mock_hass):
    """Returning to IDLE after charging should call the charge stop script."""
    # First go to charge
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.reset_mock()
    
    # Then go to IDLE
    await executor.apply_state(STATE_IDLE, limit_kw=0.0)
    assert executor.last_state == STATE_IDLE
    mock_hass.services.async_call.assert_any_call(
        "script", "turn_on", {"entity_id": "script.charge_stop"}
    )


@pytest.mark.asyncio
async def test_discharge_grid_calls_discharge_script(executor, mock_hass):
    """DISCHARGE_GRID should call the discharge script."""
    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    assert executor.last_state == STATE_DISCHARGE_GRID
    mock_hass.services.async_call.assert_called_with(
        "script", "turn_on", {"entity_id": "script.force_discharge"}
    )


@pytest.mark.asyncio
async def test_idle_after_discharge_calls_discharge_stop(executor, mock_hass):
    """Returning to IDLE after discharging should call the discharge stop script."""
    # First go to discharge
    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    mock_hass.services.async_call.reset_mock()
    
    # Then go to IDLE
    await executor.apply_state(STATE_IDLE, limit_kw=0.0)
    assert executor.last_state == STATE_IDLE
    mock_hass.services.async_call.assert_any_call(
        "script", "turn_on", {"entity_id": "script.discharge_stop"}
    )


@pytest.mark.asyncio
async def test_discharge_home_state(executor, mock_hass):
    """DISCHARGE_HOME (Self-Consumpiton) should return from a forced state via stop scripts."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.reset_mock()
    
    await executor.apply_state(STATE_DISCHARGE_HOME, limit_kw=5.0)
    assert executor.last_state == STATE_DISCHARGE_HOME
    mock_hass.services.async_call.assert_any_call(
        "script", "turn_on", {"entity_id": "script.charge_stop"}
    )


@pytest.mark.asyncio
async def test_preserve_state(executor):
    """PRESERVE should be tracked."""
    await executor.apply_state(STATE_PRESERVE, limit_kw=0.0)
    assert executor.last_state == STATE_PRESERVE


@pytest.mark.asyncio
async def test_charge_solar_state(executor):
    """CHARGE_SOLAR should be tracked."""
    await executor.apply_state(STATE_CHARGE_SOLAR, limit_kw=3.0)
    assert executor.last_state == STATE_CHARGE_SOLAR


@pytest.mark.asyncio
async def test_no_repeat_if_same_state(executor):
    """Should not re-apply if state hasn't changed."""
    await executor.apply_state(STATE_IDLE, limit_kw=0.0)
    result1 = executor.last_state
    await executor.apply_state(STATE_IDLE, limit_kw=0.0)
    result2 = executor.last_state
    assert result1 == result2 == STATE_IDLE
    # Should have only applied once
    assert executor.apply_count == 1


@pytest.mark.asyncio
async def test_state_change_increments_count(executor):
    """Changing state should increment the apply count."""
    await executor.apply_state(STATE_IDLE, limit_kw=0.0)
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 2


@pytest.mark.asyncio
async def test_get_command_summary(executor):
    """Should return a human-readable summary of the last command."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    summary = executor.get_command_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0
