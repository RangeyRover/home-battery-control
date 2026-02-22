"""Tests for the FSM base classes (dataclasses and ABC)."""
import pytest
from custom_components.house_battery_control.fsm.base import (
    BatteryStateMachine,
    FSMContext,
    FSMResult,
)


def test_fsm_context_creation():
    """FSMContext dataclass should construct with all required fields."""
    ctx = FSMContext(
        soc=75.0,
        solar_production=3.5,
        load_power=1.2,
        grid_voltage=240.0,
        current_price=25.5,
        forecast_solar=[{"start": "t0", "kwh": 2.5}],
        forecast_load=[{"start": "t0", "kwh": 1.0}],
        forecast_price=[{"start": "t0", "price": 10.0}],
        config={"capacity_kwh": 27.0, "inverter_limit_kw": 10.0},
    )
    assert ctx.soc == 75.0
    assert ctx.solar_production == 3.5
    assert ctx.current_price == 25.5


def test_fsm_result_creation():
    """FSMResult dataclass should construct correctly."""
    result = FSMResult(
        state="CHARGE_GRID",
        limit_kw=5.0,
        reason="Negative price",
    )
    assert result.state == "CHARGE_GRID"
    assert result.limit_kw == 5.0
    assert result.reason == "Negative price"


def test_abstract_class_cannot_instantiate():
    """BatteryStateMachine ABC should not be directly instantiable."""
    with pytest.raises(TypeError):
        BatteryStateMachine()


def test_concrete_implementation():
    """A concrete subclass should work when calculate_next_state is implemented."""

    class TestFSM(BatteryStateMachine):
        def calculate_next_state(self, context: FSMContext) -> FSMResult:
            return FSMResult(state="IDLE", limit_kw=0.0, reason="Test")

    fsm = TestFSM()
    ctx = FSMContext(
        soc=50.0,
        solar_production=0.0,
        load_power=1.0,
        grid_voltage=240.0,
        current_price=10.0,
        forecast_solar=[],
        forecast_load=[],
        forecast_price=[],
        config={"capacity_kwh": 27.0, "inverter_limit_kw": 10.0},
    )
    result = fsm.calculate_next_state(ctx)
    assert result.state == "IDLE"
    assert result.reason == "Test"
