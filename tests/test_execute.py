"""Tests for the Execute module — translates FSM states into Powerwall commands.

Updated for Feature 07: Executor State Cleanup.
Tests the 4-state transition-aware command logic.
Updated for Feature 064: 5-Minute Settlement-Slot Keepalive & Reversal Safety.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.house_battery_control.const import (
    CONF_OBSERVATION_MODE,
    CONF_SCRIPT_CHARGE,
    CONF_SCRIPT_CHARGE_STOP,
    CONF_SCRIPT_DISCHARGE,
    CONF_SCRIPT_DISCHARGE_STOP,
    STATE_CHARGE_GRID,
    STATE_DISCHARGE_GRID,
    STATE_ERROR,
    STATE_SELF_CONSUMPTION,
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
async def test_discharge_grid_calls_discharge_script(executor, mock_hass):
    """DISCHARGE_GRID should call the discharge script."""
    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    assert executor.last_state == STATE_DISCHARGE_GRID
    mock_hass.services.async_call.assert_called_with(
        "script", "turn_on", {"entity_id": "script.force_discharge"}
    )


# --- Transition-aware stop tests ---


@pytest.mark.asyncio
async def test_self_consumption_after_charge_calls_only_charge_stop(executor, mock_hass):
    """CHARGE_GRID → SELF_CONSUMPTION should call only charge_stop (not discharge_stop)."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.reset_mock()

    await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    assert executor.last_state == STATE_SELF_CONSUMPTION
    mock_hass.services.async_call.assert_called_once_with(
        "script", "turn_on", {"entity_id": "script.charge_stop"}
    )


@pytest.mark.asyncio
async def test_self_consumption_after_discharge_calls_only_discharge_stop(executor, mock_hass):
    """DISCHARGE_GRID → SELF_CONSUMPTION should call only discharge_stop (not charge_stop)."""
    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    mock_hass.services.async_call.reset_mock()

    await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    assert executor.last_state == STATE_SELF_CONSUMPTION
    mock_hass.services.async_call.assert_called_once_with(
        "script", "turn_on", {"entity_id": "script.discharge_stop"}
    )


@pytest.mark.asyncio
async def test_self_consumption_from_idle_no_calls(executor, mock_hass):
    """SELF_CONSUMPTION when nothing was active → no script calls."""
    await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    assert executor.last_state == STATE_SELF_CONSUMPTION
    # No stop commands needed — nothing was active
    mock_hass.services.async_call.assert_not_called()


@pytest.mark.asyncio
async def test_charge_to_discharge_stops_charge_first(executor, mock_hass):
    """CHARGE_GRID → DISCHARGE_GRID should stop charge (blocking=True) then start discharge."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.reset_mock()

    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    calls = mock_hass.services.async_call.call_args_list
    assert len(calls) == 2
    # First call: stop charge (blocking=True to prevent race with new dispatch)
    assert calls[0] == (
        ("script", "turn_on", {"entity_id": "script.charge_stop"}),
        {"blocking": True},
    )
    # Second call: start discharge
    assert calls[1] == (("script", "turn_on", {"entity_id": "script.force_discharge"}),)


@pytest.mark.asyncio
async def test_discharge_to_charge_stops_discharge_first(executor, mock_hass):
    """DISCHARGE_GRID → CHARGE_GRID should stop discharge (blocking=True) then start charge."""
    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    mock_hass.services.async_call.reset_mock()

    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    calls = mock_hass.services.async_call.call_args_list
    assert len(calls) == 2
    # First call: stop discharge (blocking=True to prevent race with new dispatch)
    assert calls[0] == (
        ("script", "turn_on", {"entity_id": "script.discharge_stop"}),
        {"blocking": True},
    )
    # Second call: start charge
    assert calls[1] == (("script", "turn_on", {"entity_id": "script.force_charge"}),)


# --- ERROR state tests ---


@pytest.mark.asyncio
async def test_error_after_charge_stops_charge(executor, mock_hass):
    """ERROR after CHARGE_GRID should call charge_stop."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.reset_mock()

    await executor.apply_state(STATE_ERROR, limit_kw=0.0)
    mock_hass.services.async_call.assert_called_once_with(
        "script", "turn_on", {"entity_id": "script.charge_stop"}
    )


@pytest.mark.asyncio
async def test_error_after_discharge_stops_discharge(executor, mock_hass):
    """ERROR after DISCHARGE_GRID should call discharge_stop."""
    await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=5.0)
    mock_hass.services.async_call.reset_mock()

    await executor.apply_state(STATE_ERROR, limit_kw=0.0)
    mock_hass.services.async_call.assert_called_once_with(
        "script", "turn_on", {"entity_id": "script.discharge_stop"}
    )


# --- Dedup and observation mode ---


@pytest.mark.asyncio
async def test_no_repeat_if_same_state(executor, mock_hass):
    """Should not re-apply if state hasn't changed."""
    await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    assert executor.apply_count == 1


@pytest.mark.asyncio
async def test_state_change_increments_count(executor):
    """Changing state should increment the apply count."""
    await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 2


@pytest.mark.asyncio
async def test_get_command_summary(executor):
    """Should return a human-readable summary of the last command."""
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    summary = executor.get_command_summary()
    assert isinstance(summary, str)
    assert len(summary) > 0


# --- Observation mode tests (Feature 009) ---


@pytest.mark.asyncio
async def test_observation_mode_suppresses_execution(mock_hass):
    """Commands should NOT be called when observation_mode is True."""
    config = {
        CONF_SCRIPT_CHARGE: "script.force_charge",
        CONF_OBSERVATION_MODE: True,
    }
    executor = PowerwallExecutor(mock_hass, config)
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)

    # State should be tracked for dashboard
    assert executor.last_state == STATE_CHARGE_GRID
    # But no service call should be made
    mock_hass.services.async_call.assert_not_called()
    # Executed state should remain None
    assert executor.last_executed_state is None
    # Apply count should NOT increment (no actual execution)
    assert executor.apply_count == 0


@pytest.mark.asyncio
async def test_observation_mode_exit_triggers_execution(mock_hass):
    """Toggling observation_mode OFF should allow the next call to execute."""
    config = {
        CONF_SCRIPT_CHARGE: "script.force_charge",
        CONF_OBSERVATION_MODE: True,
    }
    executor = PowerwallExecutor(mock_hass, config)

    # Call while in observation mode — suppressed
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.assert_not_called()

    # Toggle observation mode OFF
    config[CONF_OBSERVATION_MODE] = False

    # Same state called again — should NOW execute because _last_executed_state is None
    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.assert_called_with(
        "script", "turn_on", {"entity_id": "script.force_charge"}
    )
    assert executor.apply_count == 1
    assert executor.last_executed_state == STATE_CHARGE_GRID


@pytest.mark.asyncio
async def test_observation_mode_dedup_after_real_execution(mock_hass):
    """After real execution, same state in same settlement slot should be deduped."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    config = {
        CONF_SCRIPT_CHARGE: "script.force_charge",
        CONF_OBSERVATION_MODE: False,
    }
    executor = PowerwallExecutor(mock_hass, config)
    fixed_now = datetime(2026, 11, 16, 0, 30, 10, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=fixed_now):
        # First call — executes
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
        assert executor.apply_count == 1
        mock_hass.services.async_call.reset_mock()

        # Second call in same settlement slot — deduped
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
        assert executor.apply_count == 1  # No increment
        mock_hass.services.async_call.assert_not_called()


# --- Feature 064: 5-Minute Settlement-Slot Keepalive & Reversal Safety ---


@pytest.mark.asyncio
async def test_active_charge_renews_across_settlement_slots(executor, mock_hass):
    """US1: CHARGE_GRID re-executes once per 5-minute NEM settlement slot (Adelaide +10:30 aligned)."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    # 11:00:06, 11:05:08, 11:10:15 ACDT (+10:30) == 00:30:06Z, 00:35:08Z, 00:40:15Z UTC
    t_slot_1 = datetime(2026, 11, 16, 0, 30, 6, tzinfo=timezone.utc)
    t_slot_2 = datetime(2026, 11, 16, 0, 35, 8, tzinfo=timezone.utc)
    t_slot_3 = datetime(2026, 11, 16, 0, 40, 15, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_slot_1):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 1

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_slot_2):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 2

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_slot_3):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 3

    assert mock_hass.services.async_call.call_count == 3
    for c in mock_hass.services.async_call.call_args_list:
        assert c == (("script", "turn_on", {"entity_id": "script.force_charge"}),)


@pytest.mark.asyncio
async def test_active_discharge_renews_across_settlement_slots(executor, mock_hass):
    """US1: DISCHARGE_GRID re-executes once per 5-minute NEM settlement slot."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    t_slot_1 = datetime(2026, 11, 16, 0, 30, 10, tzinfo=timezone.utc)
    t_slot_2 = datetime(2026, 11, 16, 0, 35, 15, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_slot_1):
        await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=10.0)
    assert executor.apply_count == 1

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_slot_2):
        await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=10.0)
    assert executor.apply_count == 2
    assert mock_hass.services.async_call.call_count == 2
    for c in mock_hass.services.async_call.call_args_list:
        assert c == (("script", "turn_on", {"entity_id": "script.force_discharge"}),)


@pytest.mark.asyncio
async def test_intra_slot_suppression_across_push_clock_and_limit_jitter(executor, mock_hass):
    """US2: Within the same 5-min slot, suppress repeats across :XX:06 push, :XX:15 clock, and limit_kw drift."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    # All 4 timestamps belong to the 00:35:00Z..00:39:59Z (11:05 ACDT) settlement slot
    t_push = datetime(2026, 11, 16, 0, 35, 6, tzinfo=timezone.utc)
    t_clock = datetime(2026, 11, 16, 0, 35, 15, tzinfo=timezone.utc)
    t_soc_1 = datetime(2026, 11, 16, 0, 37, 30, tzinfo=timezone.utc)
    t_soc_2 = datetime(2026, 11, 16, 0, 39, 59, tzinfo=timezone.utc)
    t_next_slot = datetime(2026, 11, 16, 0, 40, 5, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_push):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert executor.apply_count == 1

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_clock):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_soc_1):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=5.4)
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_soc_2):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=4.9)

    assert executor.apply_count == 1
    assert mock_hass.services.async_call.call_count == 1
    assert "4.9 kW" in executor.get_command_summary()

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_next_slot):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=4.9)
    assert executor.apply_count == 2
    assert mock_hass.services.async_call.call_count == 2


@pytest.mark.asyncio
async def test_mid_slot_state_transition_executes_immediately(executor, mock_hass):
    """US2: A genuine state change inside the same 5-minute slot executes immediately."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    t_1 = datetime(2026, 11, 16, 0, 35, 6, tzinfo=timezone.utc)
    t_2 = datetime(2026, 11, 16, 0, 35, 12, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_1):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    mock_hass.services.async_call.reset_mock()

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_2):
        await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)

    assert executor.apply_count == 2
    mock_hass.services.async_call.assert_called_once_with(
        "script", "turn_on", {"entity_id": "script.charge_stop"}
    )


@pytest.mark.asyncio
async def test_passive_states_never_repeat_across_settlement_slots(executor, mock_hass):
    """US3: SELF_CONSUMPTION and ERROR remain strictly one-and-done across future settlement slots."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    t_0 = datetime(2026, 11, 16, 0, 30, 10, tzinfo=timezone.utc)
    t_1 = datetime(2026, 11, 16, 0, 35, 15, tzinfo=timezone.utc)
    t_2 = datetime(2026, 11, 16, 0, 40, 15, tzinfo=timezone.utc)
    t_3 = datetime(2026, 11, 16, 0, 45, 15, tzinfo=timezone.utc)
    t_4 = datetime(2026, 11, 16, 0, 50, 15, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_0):
        await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_1):
        await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    mock_hass.services.async_call.reset_mock()

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_2):
        await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_3):
        await executor.apply_state(STATE_SELF_CONSUMPTION, limit_kw=0.0)
    mock_hass.services.async_call.assert_not_called()
    assert executor.apply_count == 2

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_3):
        await executor.apply_state(STATE_ERROR, limit_kw=0.0)
    assert executor.apply_count == 3
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_4):
        await executor.apply_state(STATE_ERROR, limit_kw=0.0)
    assert executor.apply_count == 3


@pytest.mark.asyncio
async def test_keepalive_disabled_config_preserves_one_and_done(mock_hass, config):
    """US3: Setting executor_keepalive_enabled=False restores legacy one-and-done behavior."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    from custom_components.house_battery_control.const import CONF_EXECUTOR_KEEPALIVE_ENABLED

    cfg = {**config, CONF_EXECUTOR_KEEPALIVE_ENABLED: False}
    exec_legacy = PowerwallExecutor(mock_hass, cfg)

    t_1 = datetime(2026, 11, 16, 0, 30, 10, tzinfo=timezone.utc)
    t_2 = datetime(2026, 11, 16, 0, 35, 15, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_1):
        await exec_legacy.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_2):
        await exec_legacy.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)

    assert exec_legacy.apply_count == 1
    assert mock_hass.services.async_call.call_count == 1


@pytest.mark.asyncio
async def test_observation_mode_suppresses_across_settlement_slots(mock_hass, config):
    """US3: Observation mode suppresses across slots and fires immediately once disabled."""
    from datetime import datetime, timezone
    from unittest.mock import patch

    cfg = {**config, CONF_OBSERVATION_MODE: True}
    exec_obs = PowerwallExecutor(mock_hass, cfg)

    t_1 = datetime(2026, 11, 16, 0, 30, 10, tzinfo=timezone.utc)
    t_2 = datetime(2026, 11, 16, 0, 35, 15, tzinfo=timezone.utc)
    t_3 = datetime(2026, 11, 16, 0, 37, 0, tzinfo=timezone.utc)

    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_1):
        await exec_obs.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_2):
        await exec_obs.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)

    mock_hass.services.async_call.assert_not_called()
    assert exec_obs.apply_count == 0
    assert exec_obs.last_executed_state is None

    cfg[CONF_OBSERVATION_MODE] = False
    with patch("custom_components.house_battery_control.execute.dt_util.utcnow", return_value=t_3):
        await exec_obs.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)
    assert exec_obs.apply_count == 1
    mock_hass.services.async_call.assert_called_once_with(
        "script", "turn_on", {"entity_id": "script.force_charge"}
    )


@pytest.mark.asyncio
async def test_direct_reversal_stop_timeout_still_starts_new_state(executor, mock_hass):
    """US3: If blocking transitional stop times out, executor logs warning and still starts opposite state."""
    import asyncio
    from unittest.mock import patch

    await executor.apply_state(STATE_CHARGE_GRID, limit_kw=6.3)

    async def slow_stop_then_fast_start(domain, service, data, **kwargs):
        if data.get("entity_id") == "script.charge_stop":
            await asyncio.sleep(0.2)

    mock_hass.services.async_call = AsyncMock(side_effect=slow_stop_then_fast_start)

    with patch("custom_components.house_battery_control.execute.DEFAULT_STOP_SCRIPT_TIMEOUT", 0.01):
        await executor.apply_state(STATE_DISCHARGE_GRID, limit_kw=10.0)

    calls = mock_hass.services.async_call.call_args_list
    assert len(calls) == 2
    assert calls[0] == (
        ("script", "turn_on", {"entity_id": "script.charge_stop"}),
        {"blocking": True},
    )
    assert calls[1] == (("script", "turn_on", {"entity_id": "script.force_discharge"}),)
    assert executor.last_executed_state == STATE_DISCHARGE_GRID
