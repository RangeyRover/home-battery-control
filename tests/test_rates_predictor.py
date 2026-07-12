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

    def test_analog_search_extracts_288_curves(self, mock_hass):
        """Principle: Extracted analog curves must be exactly 288 steps long."""
        predictor = SyntheticRatesPredictor(mock_hass)
        from unittest.mock import patch

        # We test the pure python logic, by mocking the database queries inside _run_analog_search
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)  # metadata_id
        # Provide 5 historical days matching exactly 35.0 kWh
        fake_db_yields = []
        for i in range(1, 6):
            # start_ts, max, mean, state
            fake_db_yields.append((datetime(2026, 1, i, tzinfo=datetime.now().astimezone().tzinfo).timestamp(), 35.0, None, None))
        mock_result.fetchall.return_value = fake_db_yields

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        with (
            patch("custom_components.house_battery_control.rates_predictor.get_instance") as mock_get_instance,
            patch("custom_components.house_battery_control.rates_predictor.history.get_significant_states") as mock_history
        ):
            mock_get_instance.return_value.engine = mock_engine
            # Mock empty history to force LTS fallback which returns empty curves (zeros)
            mock_history.return_value = {}

            analog_days = predictor._run_analog_search(35.0)

            assert len(analog_days) == 5
            for day in analog_days:
                assert len(day.pricing_curve) == 288
                assert len(day.export_curve) == 288
                assert len(day.load_curve) == 288

    def test_analog_search_graceful_degradation(self, mock_hass):
        """Principle: If no days are within 5% tolerance, degrades to 5 closest days."""
        predictor = SyntheticRatesPredictor(mock_hass)
        from unittest.mock import patch

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)  # metadata_id
        # Provide historical days way outside the 5% tolerance for 35.0
        # Target = 35.0. 5% tolerance = 1.75 (33.25 to 36.75)
        # Or minimum tolerance 2.0 (33.0 to 37.0). Let's provide days far away.
        fake_db_yields = [
            (datetime(2026, 1, 1).timestamp(), 10.0, None, None),
            (datetime(2026, 1, 2).timestamp(), 12.0, None, None),
            (datetime(2026, 1, 3).timestamp(), 14.0, None, None),
            (datetime(2026, 1, 4).timestamp(), 16.0, None, None),
            (datetime(2026, 1, 5).timestamp(), 18.0, None, None),
            (datetime(2026, 1, 6).timestamp(), 20.0, None, None), # Should pick 12, 14, 16, 18, 20
        ]
        mock_result.fetchall.return_value = fake_db_yields

        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        with (
            patch("custom_components.house_battery_control.rates_predictor.get_instance") as mock_get_instance,
            patch("custom_components.house_battery_control.rates_predictor.history.get_significant_states") as mock_history
        ):
            mock_get_instance.return_value.engine = mock_engine
            mock_history.return_value = {}

            analog_days = predictor._run_analog_search(35.0)

            assert len(analog_days) == 5
            yields = [d.pv_yield for d in analog_days]
            assert 10.0 not in yields # Furthest away should be dropped
            assert 20.0 in yields # Closest should be included
