from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from custom_components.house_battery_control.rates_predictor import (
    AnalogDay,
    SyntheticRatesPredictor,
)


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.states.get.return_value = MagicMock(state="35.0")
    hass.async_add_executor_job = AsyncMock()
    return hass

class TestSyntheticRatesPredictor:
    def test_init_sets_up_state(self, mock_hass):
        predictor = SyntheticRatesPredictor(mock_hass)
        assert predictor._hass == mock_hass
        assert predictor._last_calculated_solar_kwh is None

    @pytest.mark.asyncio
    async def test_check_solcast_bypasses_if_within_tolerance(self, mock_hass):
        predictor = SyntheticRatesPredictor(mock_hass)
        predictor._last_calculated_solar_kwh = 34.0  # Within 2 kWh of 35.0

        await predictor.async_check_and_update()

        mock_hass.async_add_executor_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_solcast_triggers_if_outside_tolerance(self, mock_hass):
        predictor = SyntheticRatesPredictor(mock_hass)
        predictor._last_calculated_solar_kwh = 30.0  # 5 kWh diff from 35.0

        analog_days = [
            AnalogDay(
                date=datetime(2025, 1, i),
                pv_yield=35.0,
                pricing_curve=[float(i)]*288,
                export_curve=[float(i)*2]*288,
                load_curve=[100.0]*288
            ) for i in range(1, 6)
        ]
        mock_hass.async_add_executor_job.return_value = analog_days

        await predictor.async_check_and_update()

        assert mock_hass.async_add_executor_job.call_count == 1
        assert predictor.synthesized_pricing_curve == [3.0] * 288
        assert predictor.synthesized_export_curve == [6.0] * 288
        assert predictor.synthesized_load_curve == [100.0] * 288

