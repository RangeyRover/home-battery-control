from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from custom_components.house_battery_control.coordinator import HBCDataUpdateCoordinator
from homeassistant.util import dt as dt_util


@pytest.mark.asyncio
async def test_solver_synthetic_integration():
    """Test that solver_inputs is extended correctly with synthetic data."""
    hass = MagicMock()
    config = {
        "battery_capacity": 27.0,
        "battery_power_entity": "sensor.battery_power",
        "solar_entity": "sensor.solar_power",
        "grid_entity": "sensor.grid_power",
        "load_today_entity": "sensor.load_today",
        "import_today_entity": "sensor.import_today",
        "export_today_entity": "sensor.export_today",
    }
    config_entry = MagicMock()
    telemetry_tracker = MagicMock()

    now = dt_util.now().replace(minute=0, second=0, microsecond=0)
    rates_list = []
    for i in range(100):
        rates_list.append({
            "start": now + timedelta(minutes=5 * i),
            "end": now + timedelta(minutes=5 * (i + 1)),
            "import_price": 0.20,
            "export_price": 0.05
        })

    synthetic_pricing_curve = [0.15] * 288
    synthetic_export_curve = [0.04] * 288
    synthetic_load_curve = [2.0] * 288

    with patch.object(HBCDataUpdateCoordinator, "__init__", return_value=None):
        coordinator = HBCDataUpdateCoordinator(hass, config_entry, config, telemetry_tracker)
        coordinator.hass = hass
        coordinator.config = config

        extended_rates = list(rates_list)
        last_rate = extended_rates[-1]["start"]
        target_end = (dt_util.now() + timedelta(days=1)).replace(hour=23, minute=55, second=0, microsecond=0)

        current = last_rate + timedelta(minutes=5)
        while current <= target_end:
            tod_idx = (current.hour * 60 + current.minute) // 5
            extended_rates.append({
                "start": current,
                "end": current + timedelta(minutes=5),
                "import_price": synthetic_pricing_curve[tod_idx],
                "export_price": synthetic_export_curve[tod_idx],
                "synthetic": True,
                "synthetic_load_kw": synthetic_load_curve[tod_idx]
            })
            current += timedelta(minutes=5)

        solver_inputs = coordinator._build_solver_inputs(
            rates_list=extended_rates,
            forecast_load=[],
            forecast_solar=[],
            current_price=0.20,
            current_export_price=0.05
        )

    last_rate_start = rates_list[-1]["start"]
    target_end = (dt_util.now() + timedelta(days=1)).replace(hour=23, minute=55, second=0, microsecond=0)

    expected_extension = int((target_end - (last_rate_start + timedelta(minutes=5))).total_seconds() / 300) + 1
    if expected_extension < 0:
        expected_extension = 0

    expected_total_length = len(rates_list) + expected_extension

    print(f"Rates length: {len(rates_list)}")
    print(f"Expected total length: {expected_total_length}")
    print(f"Actual price_buy length: {len(solver_inputs.price_buy)}")

    assert len(solver_inputs.price_buy) > 288, "Solver inputs were not dynamically extended!"
    assert len(solver_inputs.price_buy) == expected_total_length, "Solver inputs length did not match expected dynamic length!"
    assert len(solver_inputs.load_kwh) == expected_total_length
    assert len(solver_inputs.pv_kwh) == expected_total_length
