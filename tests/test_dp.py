import pytest
from custom_components.house_battery_control.fsm.base import FSMContext
from custom_components.house_battery_control.fsm.dp_fsm import DpBatteryStateMachine


@pytest.fixture
def fsm():
    return DpBatteryStateMachine()


@pytest.fixture
def mock_context():
    # Construct a 288-step matrix for a highly simplified day
    # Prices: 10c import, 8c export baseline.
    # Peak: 50c import, 40c export from index 200 to 220 (approx 5pm)
    prices = []
    solar = []
    load = []

    for i in range(288):
        # Base
        price = {"import_price": 10.0, "export_price": 8.0}
        pv_kw = 0.0
        ld_kw = 1.0

        # Noon Solar (index 120-140)
        if 120 <= i <= 140:
            pv_kw = 5.0

        # Evening Peak (index 180-200)
        if 180 <= i <= 200:
            price = {"import_price": 50.0, "export_price": 40.0}
            ld_kw = 3.0

        prices.append(price)
        solar.append({"kw": pv_kw})
        load.append({"kw": ld_kw})

    context = FSMContext(
        soc=20.0,  # 20%
        solar_production=0.0,
        load_power=1.0,
        grid_voltage=240.0,
        current_price=10.0,
        forecast_solar=solar,
        forecast_load=load,
        forecast_price=prices,
        config={"capacity_kwh": 13.5, "inverter_limit_kw": 5.0},
    )
    return context


def test_dp_charges_before_peak(fsm, mock_context):
    """
    Test that the DP battery engine correctly solves to charge from the grid
    if there is a massive evening peak and no midday solar.
    """
    # Remove all solar from the forecast to force it to buy off the grid
    for i in range(288):
        mock_context.forecast_solar[i] = {"kw": 0.0}

    # Ask the FSM what to do at index 0
    # It should immediately realize it needs to charge from the grid at 10c
    # to avoid paying 50c later tonight!
    result = fsm.calculate_next_state(mock_context)

    assert result.state == "CHARGE_GRID", result.reason
    assert result.limit_kw > 0.0


def test_dp_negative_export_trap(fsm, mock_context):
    """
    Test the specific 'Negative Export Trap' edgecase defined in the system requirements.
    At index 0 (morning), prices are normal.
    At index 100 (midday), there is heavy solar, but the export price drops to -50c.
    The battery MUST charge at midday.
    Because of this, it MUST NOT charge from the grid at index 0, even though it's cheap,
    because it needs to save room for the midday sponge.
    """
    # 1. Start the battery nearly full
    mock_context.soc = 90.0

    # 2. Add an extreme negative export price during the solar midday window
    for i in range(120, 140):
        mock_context.forecast_solar[i] = {"kw": 6.0}
        mock_context.forecast_load[i] = {"kw": 0.0}
        mock_context.forecast_price[i] = {"import_price": 10.0, "export_price": -50.0}

    # 3. Add heavy solar right now (index 0) with normal export (8c)
    mock_context.forecast_solar[0] = {"kw": 6.0}
    mock_context.solar_production = 6.0
    mock_context.forecast_load[0] = {"kw": 0.0}
    mock_context.load_power = 0.0

    # FIX: Remove all house load between now and the toxic solar.
    # Otherwise, the DP solver is smart enough to realize it can drain the battery into the house,
    # freeing up space for the toxic solar later! We want to test a TRUE trap.
    for i in range(1, 120):
        mock_context.forecast_load[i] = {"kw": 0.0}

    # Normally, if SoC is 90% and we have excess solar, the Greedy FSM rule says "CHARGE_SOLAR"
    # But solving the next 24 hours, the DP engine should realize "Wait, if I charge now, I won't have room
    # for the toxic -50c solar in 120 steps. I must 'IDLE' (or export normally) right now so the battery
    # is ready later."
    result = fsm.calculate_next_state(mock_context)

    with open("dp_debug.txt", "w") as f:
        f.write(str(fsm.controller.optimizer.policy))

    # The absolute optimal move is to NOT charge the battery right now, leaving it at 90%
    # so there is space for the toxic solar later.
    assert result.state == "IDLE"


def test_dp_fallback_config_keys(fsm, mock_context):
    """
    Test that the DP FSM gracefully accepts the integration constant config keys
    (`battery_capacity`, `inverter_limit`) when the older test keys (`capacity_kwh`,
    `inverter_limit_kw`) are missing.
    """
    # Force the mock config to ONLY use the integration keys
    mock_context.config = {"battery_capacity": 10.0, "inverter_limit": 5.0}

    # Normally this would raise a KeyError before the fix
    try:
        result = fsm.calculate_next_state(mock_context)
    except KeyError as e:
        pytest.fail(f"FSM crashed with KeyError on config access: {e}")

    assert result is not None
    assert isinstance(result.state, str)
