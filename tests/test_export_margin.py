import pytest
from custom_components.house_battery_control.fsm.base import FSMContext, SolverInputs
from custom_components.house_battery_control.fsm.dp_fsm import DpBatteryStateMachine
from custom_components.house_battery_control.fsm.lin_fsm import LinearBatteryStateMachine


@pytest.fixture
def mock_context():
    prices = []
    solar = []
    load = []

    for i in range(288):
        # Normal baseline
        price = {"import_price": 0.20, "export_price": 0.05}
        pv_kw = 0.0
        ld_kw = 0.0

        # Create an artificial peak in exactly one hour (index 12 to 24)
        if 12 <= i <= 24:
            # Export price spikes to 0.25! Very profitable normally.
            price = {"import_price": 0.30, "export_price": 0.25}

        # Create an overnight load (index 200) that requires import if battery is empty
        if 200 <= i <= 220:
            ld_kw = 2.0
            price = {"import_price": 0.20, "export_price": 0.05}

        prices.append(price)
        solar.append({"kw": pv_kw})
        load.append({"kw": ld_kw})

    context = FSMContext(
        soc=15.0,  # Just enough for the overnight load
        solar_production=0.0,
        load_power=0.0,
        grid_voltage=240.0,
        current_price=0.20,
        forecast_solar=solar,
        forecast_load=load,
        forecast_price=prices,
        config={
            "battery_capacity": 13.5,
            "inverter_limit": 5.0,
            "export_margin": 0.0,
            "round_trip_efficiency": 1.0 # 100% to keep math simple
        },
    )
    # Populate solver inputs for LP
    context.solver_inputs = SolverInputs(
        price_buy=[float(p["import_price"]) for p in prices],
        price_sell=[float(p["export_price"]) for p in prices],
        pv_kwh=[float(s["kw"]) * (5/60) for s in solar],
        load_kwh=[float(ld["kw"]) * (5/60) for ld in load],
    )
    return context


def test_export_margin_blocks_dp_export(mock_context):
    fsm = DpBatteryStateMachine()

    # Move to the start of the peak (index 12)
    mock_context.forecast_price = mock_context.forecast_price[12:]
    mock_context.forecast_solar = mock_context.forecast_solar[12:]
    mock_context.forecast_load = mock_context.forecast_load[12:]

    # Without export margin, export_price of 0.25 is profitable (no future loads needed)
    result_no_margin = fsm.calculate_next_state(mock_context)
    assert result_no_margin.state == "DISCHARGE_GRID", f"DP should want to export normally, but got {result_no_margin.state}: {result_no_margin.reason}"

    # Now add an export margin of 0.10.
    # This artificially lowers the export price to 0.15, which makes it less profitable than the baseline import price of 0.20.
    # DP should now refuse to export.
    mock_context.config["export_margin"] = 0.10
    result_with_margin = fsm.calculate_next_state(mock_context)
    assert result_with_margin.state != "DISCHARGE_GRID", "DP should be blocked from exporting due to margin"


def test_export_margin_blocks_lin_export(mock_context):
    fsm = LinearBatteryStateMachine()

    # Move to the start of the peak (index 12)
    mock_context.forecast_price = mock_context.forecast_price[12:]
    mock_context.forecast_solar = mock_context.forecast_solar[12:]
    mock_context.forecast_load = mock_context.forecast_load[12:]
    mock_context.solver_inputs.price_buy = mock_context.solver_inputs.price_buy[12:]
    mock_context.solver_inputs.price_sell = mock_context.solver_inputs.price_sell[12:]
    mock_context.solver_inputs.pv_kwh = mock_context.solver_inputs.pv_kwh[12:]
    mock_context.solver_inputs.load_kwh = mock_context.solver_inputs.load_kwh[12:]
    # Provide a simple sequence for LP
    mock_context.telemetry_sequence = []

    # Without export margin, LP sees 0.25 sell vs 0.20 median buy
    result_no_margin = fsm.calculate_next_state(mock_context)
    assert result_no_margin.state == "DISCHARGE_GRID", f"LP should want to export normally, but got {result_no_margin.state}: {result_no_margin.reason}"

    # Now add an export margin of 0.10.
    # LP sees 0.25 - 0.10 = 0.15 sell opportunity vs 0.20 median buy. It will not export.
    mock_context.config["export_margin"] = 0.10
    result_with_margin = fsm.calculate_next_state(mock_context)
    assert result_with_margin.state != "DISCHARGE_GRID", "LP should be blocked from exporting due to margin"
