"""Tests for Linear Programming FSM implementation (lin_fsm)."""

import pytest
from custom_components.house_battery_control.fsm.base import FSMContext
from custom_components.house_battery_control.fsm.lin_fsm import LinearBatteryStateMachine


@pytest.fixture
def base_context():
    """Provides a basic valid FSMContext for testing."""
    def generate_dummy_forecast(val):
        return [{"kw": val} for _ in range(28)]  # Just 28 intervals for fast tests

    def generate_dummy_price(import_val, export_val):
        return [{"import_price": import_val, "export_price": export_val} for _ in range(28)]

    # Mock context fields
    context = FSMContext(
        soc=50.0,
        load_power=1.0,
        solar_production=0.0,
        grid_voltage=240.0,
        current_price=10.0,
        forecast_price=generate_dummy_price(10.0, 5.0),
        forecast_solar=generate_dummy_forecast(2.0),
        forecast_load=generate_dummy_forecast(1.5),
        config={
            "battery_capacity": 27.0,
            "battery_rate_max": 6.3,
            "inverter_limit": 10.0,
            "round_trip_efficiency": 0.90
        }
    )
    context.acquisition_cost = 0.0
    return context


def test_linear_solver_basic_execution(base_context):
    """Test 1: Ensure the solver executes without raising exceptions."""
    fsm = LinearBatteryStateMachine()
    result = fsm.calculate_next_state(base_context)

    # Asserting that the solver evaluated without crashing and returned a valid state
    assert result is not None
    assert result.state in ["IDLE", "CHARGE_GRID", "DISCHARGE_HOME", "DISCHARGE_GRID"]
    assert isinstance(result.limit_kw, float)


def test_linear_solver_target_soc_calculation(base_context):
    """Test 2: Assert solver calculates a Target SOC representing deficit on cheap import."""
    # Force the upcoming rates to be very cheap, but load is extremely high.
    # The solver should calculate that it needs to charge from grid to meet upcoming deficit.
    for i in range(28):
        base_context.forecast_price[i]["import_price"] = 0.01  # extremely cheap
        base_context.forecast_price[i]["export_price"] = 0.00
        base_context.forecast_load[i]["kw"] = 5.0  # high load
        base_context.forecast_solar[i]["kw"] = 0.0 # no solar
    # But later in the day, import goes back up to force it to charge now
    for i in range(14, 28):
        base_context.forecast_price[i]["import_price"] = 50.0

    base_context.soc = 10.0 # battery is almost empty

    fsm = LinearBatteryStateMachine()
    result = fsm.calculate_next_state(base_context)
    print("TEST 2 RESULT:", vars(result))

    # Ideally, it should choose to charge grid due to massive deficit and low cost
    assert result.state == "CHARGE_GRID"
    assert result.target_soc > 10.0  # Target SOC should be much higher to cover 5kW load


def test_inverter_physical_bounds_limit_kw(base_context):
    """Test 3: Assert the system physically clamps the charging/discharging limit_kw."""
    # Create an extreme scenario that mathematically suggests massive charge rate
    for i in range(28):
        base_context.forecast_price[i]["import_price"] = -100.0  # getting paid to charge
        base_context.forecast_price[i]["export_price"] = -100.0
        base_context.forecast_load[i]["kw"] = 0.0
        base_context.forecast_solar[i]["kw"] = 0.0

    # Must have a future positive price to make holding it worthwhile
    base_context.forecast_price[20]["import_price"] = 100.0
    base_context.forecast_load[20]["kw"] = 5.0

    base_context.soc = 10.0
    base_context.config["battery_rate_max"] = 5.0  # strictly clamp physical battery limit

    fsm = LinearBatteryStateMachine()
    result = fsm.calculate_next_state(base_context)
    print("TEST 3 RESULT:", vars(result))

    assert result.state == "CHARGE_GRID"
    # Even if mathematical optimum requires more, it is bound by `battery_rate_max`
    assert result.limit_kw <= 5.0


def test_solver_failure_fallback(base_context):
    """Test 4: Assert solver falls back to IDLE when arrays are malformed."""
    base_context.forecast_price = []  # length 0 implies missing data or crash context

    fsm = LinearBatteryStateMachine()
    result = fsm.calculate_next_state(base_context)

    # Forecast length < 1 should trigger early exit safe fallback
    assert result.state == "IDLE"
    assert result.limit_kw == 0.0
    assert result.reason == "Forecast too short"

